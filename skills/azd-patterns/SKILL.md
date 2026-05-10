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

| Module | File | Selector (SPEC § 11c key) | Outputs (always) | When to include |
|--------|------|---------------------------|------------------|-----------------|
| **cosmos** | `infra/modules/cosmos.bicep` | `cosmos: { sku: 'serverless' \| 'autoscale' }` | `endpoint`, `accountName`, `databaseName`, `containerNames[]` | Any process that needs case state, audit, or agent memory (default for ALL processes) |
| **search** | `infra/modules/search.bicep` | `search: { sku: 'basic' \| 'standard' }` | `endpoint`, `serviceName`, `indexNames[]`, `apiVersion` | Knowledge retrieval (paired with `foundry-iq` index Bicep below) |
| **doc-intel** | `infra/modules/doc-intel.bicep` | `docIntel: { tier: 'S0' }` | `endpoint`, `accountName` | Structured-doc ingestion (KYC IDs, invoices, claims forms) |
| **vision** | `infra/modules/vision.bicep` | `vision: { model: 'gpt-5.4-pro' \| 'gpt-5.4' \| 'gpt-5.4-mini' }` | `endpoint`, `deploymentName` | Image / damage-photo / blueprint analysis |
| **speech** | `infra/modules/speech.bicep` | `speech: { tier: 'S0' }` | `endpoint`, `accountName`, `region` | STT for FNOL / call recordings, TTS for IVR responses |
| **event-grid** | `infra/modules/event-grid.bicep` | `eventGrid: { topics: [...] }` | `topicEndpoints{}`, `topicResourceIds{}` | Event-driven triggers (Supplier Risk news, Order Fallout) |
| **service-bus** | `infra/modules/service-bus.bicep` | `serviceBus: { tier: 'standard' \| 'premium', queues: [...], topics: [...] }` | `namespace`, `queueNames[]`, `topicNames[]` | Async work queues (PIM enrichment batch, Card Dispute case routing) |
| **storage-blob** | `infra/modules/storage-blob.bicep` | `blob: { containers: [...] }` | `accountName`, `containerNames[]`, `endpoint` | Document/image/audio storage for vision / doc-intel / speech |
| **key-vault** | `infra/modules/key-vault.bicep` | `keyVault: { enabled: bool }` | `vaultName`, `vaultUri` | Required when external API keys must be secured (e.g., third-party data sources) |
| **app-insights** | `infra/modules/app-insights.bicep` | (always included — non-optional for Foundry agents) | `connectionString`, `instrumentationKey`, `appId` | Always — required for `foundry-evals` continuous loop |
| **aca-job** | `infra/modules/aca-job.bicep` | `acaJobs: [{ name, trigger: 'cron' \| 'manual', ... }]` | `jobName`, `jobResourceId` per entry | Wired by `threadlight-event-triggers` for receivers |
| **aca-mcp** | `infra/modules/aca-mcp.bicep` | `mcpServers: [{ name, image, ... }]` | `mcpEndpoints{}`, `mcpFqdns{}` | Wired by `foundry-mcp-aca` for each mocked or custom MCP server |
| **aca-bot** | `infra/modules/aca-bot.bicep` | `teamsBot: { enabled: bool, manifest: ... }` | `botFqdn`, `botResourceId`, `botAppId` | Wired by `foundry-teams-bot` when SPEC § 8 includes Teams |
| **foundry-iq-index** | `infra/modules/foundry-iq-index.bicep` | `foundryIQ: { knowledgeBases: [...] }` | `indexNames[]`, `agentNames[]` | **Default for every process** (per `foundry-iq` skill rule) — provisions the AI Search index + Knowledge Agent |
| **uami** | `infra/modules/uami.bicep` | (always included) | `uamiResourceId`, `uamiPrincipalId`, `uamiClientId` | Always — single shared identity per app (see Shared UAMI Pattern above) |
| **acr** | `infra/modules/acr.bicep` | `acr: { sku: 'Standard' \| 'Premium' }` | `acrEndpoint`, `acrName`, `acrResourceId` | Required when MCP / receiver / bot containers are deployed |
| **foundry-account** | `infra/modules/foundry-account.bicep` | (always included for the hosted agent) | `accountName`, `projectName`, `endpoint` | Always — hosts the agent itself |

### Selector grammar (SPEC § 11c)

The SPEC § 11c table is read as a **selector dictionary**. Each top-level key
matches a module name; the value is the module's input parameter shape. The
composer iterates and includes only present keys:

```yaml
# specs/SPEC.md § 11c (excerpted)
tech_stack:
  cosmos: { sku: serverless }
  search: { sku: basic }
  foundryIQ:
    knowledgeBases:
      - name: kyc-policies
        sources: [{ type: blob, container: policies, prefix: kyc/ }]
  vision: { model: gpt-5.4-mini }
  acaJobs:
    - { name: sla-watcher, trigger: cron, schedule: "*/15 * * * *" }
  mcpServers:
    - { name: customer-data-mcp, image: customer-mcp:latest }
  teamsBot: { enabled: true }
  citadel: { required: false }   # opt-in via citadel-spoke-onboarding
```

Resulting `infra/main.bicep` includes (in canonical order):
`uami → acr → key-vault → app-insights → cosmos → search → foundry-iq-index → vision → doc-intel → speech → storage-blob → event-grid → service-bus → aca-mcp → aca-job → foundry-account → aca-bot`.

### Why composable modules (not one big main.bicep)

- **Per-process repos vary widely** — KYC needs `doc-intel + speech + foundry-iq`;
  Order Fallout needs `service-bus + aca-job + aca-mcp`. A single template would
  bury 70% of the file in `if` blocks per module.
- **Customer can adopt modules incrementally** — they may already have a Cosmos
  account they want to reuse; replacing one module file is cleaner than editing
  a monolith.
- **Each module is independently versionable** — when AI Search v2025-09 ships
  a new index schema, only `search.bicep` changes.

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

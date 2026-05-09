---
name: azure-tenant-isolation
description: >
  Multi-tenant Azure CLI and AZD isolation for concurrent terminal sessions.
  Index-file driven, bare `az` CLI commands only — no wrapper scripts, no
  PowerShell modules. Mandatory two-layer guard: per-tenant `AZURE_CONFIG_DIR`
  is the foundation, and `az account show` assertion is the extra gate that
  verifies tenant + subscription before destructive operations.
  USE FOR: az login, azd up, azd deploy, az account set, Azure subscription,
  Azure tenant, AZURE_CONFIG_DIR, AZD_CONFIG_DIR, multi-tenant, switch tenant,
  deploy to Azure, Bicep deploy, az deployment, azd auth, ChainedTokenCredential,
  Azure identity, verify subscription, confirm tenant, tenant index, prevent
  cross-tenant deployment.
  DO NOT USE FOR: creating Azure resources from scratch (use azure-prepare),
  cost optimization (use azure-cost-optimization), Foundry agents (use
  microsoft-foundry).
---

# Multi-Tenant Azure CLI & AZD Isolation

Run multiple `az` / `azd` workflows against different Azure tenants and
subscriptions **at the same time** without crossing wires.

This skill ships **two files only**: this document and a JSON schema example.
There are **no wrapper scripts, no PowerShell modules, no helper functions**.
Every Azure operation in this skill is a **literal `az` (or `azd`) CLI
command**. The only shell-specific bits are the unavoidable env-var
one-liners (`export VAR=…` on Unix, `$env:VAR=…` on Windows).

---

## Problem

`az` and `azd` keep session state (tokens, active subscription, environments)
in a **single shared directory** (`~/.azure` and `~/.azd` by default). When
two terminals or scripts target different tenants concurrently they collide:

- `az login --tenant X` in terminal A overwrites the token used by terminal B.
- `az account set -s <sub>` mutates **global** state — every shell sees it.
- `azd env select` in one shell leaks into another.
- A subprocess that forgets `AZURE_CONFIG_DIR` silently hits the wrong tenant.

This is the #1 cause of "I deployed to the wrong subscription" incidents.

---

## Design — two layered guards

Tenant isolation here is built from **two stacked guards**. They are
**complementary**, not alternatives.

```
                    +-----------------------------------------+
   per-tenant       |  AZURE_CONFIG_DIR=~/.azure-tenants/prod |  ← FOUNDATION
   isolation        |  AZD_CONFIG_DIR  =~/.azd-tenants/prod   |     never replaced
                    +-----------------------------------------+
                                       |
                                       v
                    +-----------------------------------------+
   subscription     |  az account show --query tenantId -o tsv|  ← EXTRA GATE
   assertion via    |  az account show --query name     -o tsv|     compare → exit 1
   az CLI           |                                         |     on mismatch
                    +-----------------------------------------+
                                       |
                                       v
                    +-----------------------------------------+
                    |  destructive op (azd up, az deployment) |
                    +-----------------------------------------+
```

**The assertion does NOT replace the env-var setup.** Both must be present
before any destructive operation. The env vars provide isolation; the
assertion catches drift inside an isolated config dir (e.g. a stale
default subscription, or another shell that ran `az account set` against
the same config dir).

### Tenant index = single source of truth

Instead of hard-coding tenant ids in shells, scripts, or docs, keep a small
JSON file describing every tenant you work with. By default it lives at:

- `$env:AZURE_TENANT_INDEX` if set
- otherwise `~/.azure-tenants/index.json`

This file is **personal data** — it lists the tenant ids you work with and
their friendly aliases. **Gitignore it. Never commit it.**

A starter copy lives in [`references/index.example.json`](references/index.example.json).

---

## The tenant index file

Schema (excerpt — full example: [`references/index.example.json`](references/index.example.json)):

```json
{
  "version": 1,
  "default_alias": "prod",
  "tenants": {
    "prod": {
      "tenant_id": "00000000-0000-0000-0000-000000000001",
      "description": "Production tenant",
      "config_dir": null,
      "default_subscription": "acme-prod",
      "allowed_subscriptions": ["acme-prod"]
    },
    "dev": {
      "tenant_id": "00000000-0000-0000-0000-000000000002",
      "description": "Development tenant",
      "config_dir": null,
      "default_subscription": "acme-dev",
      "allowed_subscriptions": ["acme-dev", "acme-test"]
    }
  }
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `version` | int | Schema version. Currently `1`. |
| `default_alias` | string | Alias used when none is specified. |
| `tenants.<alias>.tenant_id` | string | Azure AD tenant GUID. |
| `tenants.<alias>.description` | string | Human note (free text). |
| `tenants.<alias>.config_dir` | string\|null | Override for `AZURE_CONFIG_DIR`. `null` → derive `~/.azure-tenants/<alias>`. |
| `tenants.<alias>.default_subscription` | string | Subscription name (or id) to set after login. |
| `tenants.<alias>.allowed_subscriptions` | string[] | Names (or ids) the assertion accepts. Empty → any. |

### Bootstrap — manual, no scripts

Unix:

```bash
mkdir -p ~/.azure-tenants
curl -fsSL -o ~/.azure-tenants/index.json \
  https://raw.githubusercontent.com/aiappsgbb/awesome-gbb/main/skills/azure-tenant-isolation/references/index.example.json
$EDITOR ~/.azure-tenants/index.json   # replace placeholder GUIDs / sub names
```

Windows (PowerShell):

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.azure-tenants" | Out-Null
Invoke-WebRequest `
  -Uri 'https://raw.githubusercontent.com/aiappsgbb/awesome-gbb/main/skills/azure-tenant-isolation/references/index.example.json' `
  -OutFile "$env:USERPROFILE\.azure-tenants\index.json"
notepad "$env:USERPROFILE\.azure-tenants\index.json"
```

Make sure your global `.gitignore_global` (or repo-level `.gitignore`)
excludes `.azure-tenants/` so the file never lands in a repo.

---

## Canonical `az` CLI flow

All commands below are bare `az` invocations. The only shell-specific lines
are the env-var exports (which cannot be wrapped).

### One-time tenant setup

Read the alias's `tenant_id`, `default_subscription`, and `config_dir` from
your `~/.azure-tenants/index.json`. Substitute them into the commands below.

Unix:

```bash
mkdir -p ~/.azure-tenants/prod ~/.azd-tenants/prod
export AZURE_CONFIG_DIR=~/.azure-tenants/prod
export AZD_CONFIG_DIR=~/.azd-tenants/prod
az login --tenant 00000000-0000-0000-0000-000000000001
az account set --subscription acme-prod
az account show
```

Windows:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.azure-tenants\prod" | Out-Null
New-Item -ItemType Directory -Force "$env:USERPROFILE\.azd-tenants\prod"   | Out-Null
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-tenants\prod"
$env:AZD_CONFIG_DIR   = "$env:USERPROFILE\.azd-tenants\prod"
az login --tenant 00000000-0000-0000-0000-000000000001
az account set --subscription acme-prod
az account show
```

### Switching tenants in a new shell

If you have already logged in to that tenant's config dir before, you don't
need to re-run `az login` — just point the env vars and `az` will pick up
the cached token.

Unix:

```bash
export AZURE_CONFIG_DIR=~/.azure-tenants/dev
export AZD_CONFIG_DIR=~/.azd-tenants/dev
az account show --query "{tenantId:tenantId, sub:name}" -o table
```

Windows:

```powershell
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-tenants\dev"
$env:AZD_CONFIG_DIR   = "$env:USERPROFILE\.azd-tenants\dev"
az account show --query "{tenantId:tenantId, sub:name}" -o table
```

### Inspecting the current context

```bash
echo "AZURE_CONFIG_DIR=$AZURE_CONFIG_DIR"
echo "AZD_CONFIG_DIR=$AZD_CONFIG_DIR"
az account show -o table
az account list --query "[].{name:name, tenantId:tenantId, isDefault:isDefault}" -o table
```

```powershell
"AZURE_CONFIG_DIR=$env:AZURE_CONFIG_DIR"
"AZD_CONFIG_DIR=$env:AZD_CONFIG_DIR"
az account show -o table
az account list --query "[].{name:name, tenantId:tenantId, isDefault:isDefault}" -o table
```

---

## The mandatory verify-before-act pattern

Before **any** destructive operation (`azd up`, `azd deploy`,
`az deployment ... create`, `az group create`, `az resource delete`,
container/job image updates, etc.), run the assertion below. It uses
**only** `az` CLI — no scripts or wrappers.

Unix:

```bash
EXPECTED_TENANT=00000000-0000-0000-0000-000000000001
EXPECTED_SUB=acme-prod

ACTUAL_TENANT=$(az account show --query tenantId -o tsv)
ACTUAL_SUB=$(az account show --query name -o tsv)

[ "$ACTUAL_TENANT" = "$EXPECTED_TENANT" ] || { echo "❌ Tenant mismatch (got $ACTUAL_TENANT, expected $EXPECTED_TENANT)"; exit 1; }
[ "$ACTUAL_SUB"    = "$EXPECTED_SUB"    ] || { echo "❌ Sub mismatch (got $ACTUAL_SUB, expected $EXPECTED_SUB)"; exit 1; }

echo "✅ Verified: $ACTUAL_SUB on tenant $ACTUAL_TENANT"
# … destructive op here …
```

Windows:

```powershell
$expectedTenant = '00000000-0000-0000-0000-000000000001'
$expectedSub    = 'acme-prod'

$actualTenant = az account show --query tenantId -o tsv
$actualSub    = az account show --query name     -o tsv

if ($actualTenant -ne $expectedTenant) { Write-Error "Tenant mismatch (got $actualTenant, expected $expectedTenant)"; exit 1 }
if ($actualSub    -ne $expectedSub)    { Write-Error "Sub mismatch (got $actualSub, expected $expectedSub)"; exit 1 }

Write-Host "✅ Verified: $actualSub on tenant $actualTenant"
# … destructive op here …
```

> **Reminder.** This assertion **does not replace** `AZURE_CONFIG_DIR` /
> `AZD_CONFIG_DIR`. It runs **on top** of them. Without the env vars the
> assertion would just be checking the global `~/.azure` context, which is
> exactly what we want to avoid.

### Bad ↔ Good

❌ Verifying without isolation:

```bash
# config dir defaults to ~/.azure — shared with every other shell
az account set --subscription acme-prod
az account show --query name -o tsv   # checks the global state, not yours
azd up                                 # ← could deploy from any leaked context
```

✅ Isolation **then** verification:

```bash
export AZURE_CONFIG_DIR=~/.azure-tenants/prod
export AZD_CONFIG_DIR=~/.azd-tenants/prod
az account set --subscription acme-prod
[ "$(az account show --query name -o tsv)" = "acme-prod" ] || exit 1
azd up
```

---

## AZD specifics

`azd` reads its own config from `AZD_CONFIG_DIR`, but it picks up the Azure
identity from `AZURE_CONFIG_DIR` (via the same `AzureCliCredential` chain).
Always set both, in lock-step with the alias.

Unix:

```bash
export AZURE_CONFIG_DIR=~/.azure-tenants/prod
export AZD_CONFIG_DIR=~/.azd-tenants/prod
azd auth login --tenant-id 00000000-0000-0000-0000-000000000001
azd env select prod-env
azd up
```

Windows:

```powershell
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-tenants\prod"
$env:AZD_CONFIG_DIR   = "$env:USERPROFILE\.azd-tenants\prod"
azd auth login --tenant-id 00000000-0000-0000-0000-000000000001
azd env select prod-env
azd up
```

`azd env list`, `azd env select`, and the `.azure/` folder inside an `azd`
project are **separate** from `AZD_CONFIG_DIR`. They live next to your
project and travel with it. `AZD_CONFIG_DIR` only isolates the
**user-level** azd state (global config + auth cache).

---

## Bicep / direct ARM specifics

`az deployment` and friends use the same `AzureCliCredential` token, so the
isolation rules are identical:

```bash
export AZURE_CONFIG_DIR=~/.azure-tenants/prod
[ "$(az account show --query name -o tsv)" = "acme-prod" ] || exit 1
az deployment group create \
  --resource-group rg-acme \
  --template-file infra/main.bicep \
  --parameters infra/main.parameters.json
```

```powershell
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-tenants\prod"
if ((az account show --query name -o tsv) -ne 'acme-prod') { exit 1 }
az deployment group create `
  --resource-group rg-acme `
  --template-file infra/main.bicep `
  --parameters infra/main.parameters.json
```

---

## Authentication standards (cross-tenant SDK code)

When **application code** (Python, TypeScript, .NET) needs to call Azure,
prefer `ChainedTokenCredential` so local dev and production both work
without code changes. Crucially, `AzureCliCredential` (and
`AzureDeveloperCliCredential`) honour `AZURE_CONFIG_DIR`, which is what
makes per-tenant isolation work end-to-end.

```python
from azure.identity import (
    AzureDeveloperCliCredential,
    ManagedIdentityCredential,
    ChainedTokenCredential,
)

def get_azure_credential() -> ChainedTokenCredential:
    return ChainedTokenCredential(
        AzureDeveloperCliCredential(),   # local dev — reads AZURE_CONFIG_DIR
        ManagedIdentityCredential(),     # production
    )
```

```typescript
import {
  ChainedTokenCredential,
  AzureDeveloperCliCredential,
  ManagedIdentityCredential,
} from "@azure/identity";

export function getAzureCredential(): ChainedTokenCredential {
  return new ChainedTokenCredential(
    new AzureDeveloperCliCredential(),
    new ManagedIdentityCredential(),
  );
}
```

**Never use API keys when an identity option exists.** Keys break the
isolation guarantees and bypass tenant boundaries.

---

## Subprocess / script trap

A common foot-gun: a script (Python, PowerShell, Bash, Make, …) shells out
to `az` or `azd` internally. Subprocesses inherit **environment variables**
from the parent, but they do **not** inherit "the active az config" — only
the env vars do. If the parent has `AZURE_CONFIG_DIR` unset, the child uses
the global `~/.azure`, which is almost certainly the wrong tenant.

❌ Wrong:

```powershell
# AZURE_CONFIG_DIR not set in the parent → child hits ~/.azure
.\infra\scripts\publish_aca.ps1 -RG rg-acme -APP_NAME my-app
```

✅ Right:

```powershell
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-tenants\prod"
$env:AZD_CONFIG_DIR   = "$env:USERPROFILE\.azd-tenants\prod"
if ((az account show --query name -o tsv) -ne 'acme-prod') { exit 1 }
.\infra\scripts\publish_aca.ps1 -RG rg-acme -APP_NAME my-app
```

The same applies to `subprocess.run(["az", ...])` in Python, `child_process`
in Node, hooks in `azure.yaml`, GitHub Actions steps, etc. **Set the env
vars in the parent before invoking the child.**

> **Never use `az account set` to "fix" a wrong-subscription problem
> without first setting `AZURE_CONFIG_DIR`.** Without isolation, you have
> just changed the global default subscription for every other shell.

---

## Troubleshooting

| Symptom | Diagnose with `az` | Fix |
|---------|-----|-----|
| `az account show` returns wrong tenant | `az account show --query tenantId -o tsv` | Set `AZURE_CONFIG_DIR` to the right alias dir, then `az login --tenant <id>` |
| `azd up` deploys to wrong subscription | `azd env get-values \| grep AZURE_SUBSCRIPTION_ID` and `az account show --query id -o tsv` | Set both `AZURE_CONFIG_DIR` and `AZD_CONFIG_DIR`; `az account set --subscription <name>`; `azd env refresh` |
| `AADSTS50020` / `AADSTS700016` | `az account show --query tenantId` | Token from tenant A used against tenant B. Re-isolate: `rm -rf $AZURE_CONFIG_DIR; mkdir -p $AZURE_CONFIG_DIR; az login --tenant <id>` |
| `az login` opens browser unexpectedly | n/a | Always pass `--tenant <id>` so `az` skips the picker |
| Subscription not found | `az account list --query "[].{name:name,tenantId:tenantId}" -o table` | You're logged into the wrong tenant — `az login --tenant <id>` after setting `AZURE_CONFIG_DIR` |
| Multiple terminals interfering | `echo $AZURE_CONFIG_DIR` in each | Every terminal must set its own `AZURE_CONFIG_DIR` before any `az` command |
| `azd auth` token expired | `azd auth login --check-status` | `azd auth login --tenant-id <id>` (with `AZD_CONFIG_DIR` set) |
| Subprocess uses wrong tenant | `az account show` from inside the subprocess | Re-export `AZURE_CONFIG_DIR` and `AZD_CONFIG_DIR` in the parent before spawning |
| Assertion passes but deploy still wrong | `az account show --query "{sub:name, tenant:tenantId}" -o table` immediately before the deploy | Some other process changed `az account set` between assertion and deploy. Tighten by re-running the assertion immediately before each destructive call |

---

## Checklist

For a new terminal, new script, or a fresh agent session:

- [ ] `AZURE_CONFIG_DIR` is set to the tenant-specific directory.
- [ ] `AZD_CONFIG_DIR` is set if `azd` is involved.
- [ ] Logged in via `az login --tenant <id>` (and/or `azd auth login --tenant-id <id>`) — never bare `az login`.
- [ ] Default subscription set with `az account set --subscription <name>`.
- [ ] **Verification step run immediately before every destructive op:** `az account show --query tenantId -o tsv` and `--query name -o tsv` compared to expected values; `exit 1` on mismatch.
- [ ] No API keys in code — `ChainedTokenCredential` only.
- [ ] `~/.azure-tenants/index.json` is gitignored and never committed.

---

## References

- `references/index.example.json` — schema example.
- Azure CLI `--config-dir` / `AZURE_CONFIG_DIR` docs:
  <https://learn.microsoft.com/cli/azure/azure-cli-configuration#cli-configuration-file>
- `azd` env / config docs:
  <https://learn.microsoft.com/azure/developer/azure-developer-cli/manage-environment-variables>
- `azure-identity` `AzureCliCredential`:
  <https://learn.microsoft.com/python/api/azure-identity/azure.identity.azureclicredential>
- Related skills: `azd-patterns`, `foundry-cross-resource`, `threadlight-deploy`.

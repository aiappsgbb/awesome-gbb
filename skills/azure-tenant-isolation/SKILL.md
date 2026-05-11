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

### Concrete failure

Three concurrent shells targeting three different aliases — without
isolation, terminal C's `az account set` silently rewrites the active
subscription that terminal A is about to deploy with:

```
Terminal A (prod)         Terminal B (dev)          Terminal C (partner)
─────────────────         ─────────────────         ───────────────────
az login --tenant <prod>                            
                          az login --tenant <dev>   
                                                    az login --tenant <partner>
                                                    az account set -s partner-shared
az account show                                                               ← shows partner-shared (!!)
azd up                                                                         ← deploys prod env to partner sub
```

With per-terminal `AZURE_CONFIG_DIR` set to `~/.azure-tenants/{prod,dev,partner}`,
each shell has its own token cache and active sub — the writes in C never
reach A.

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

---

## Mandatory rules

These are non-negotiable. Every shell, every script, every agent session
that touches Azure must follow them.

1. **Per-tenant `AZURE_CONFIG_DIR` and `AZD_CONFIG_DIR` are mandatory.**
   Set them before the first `az` / `azd` command in every new shell.
   They are the foundation guard and are **never** replaced by anything
   downstream (assertions, `--subscription` flags, etc.).
2. **Always verify subscription before destructive operations.** Run the
   `az account show --query tenantId/name -o tsv` assertion immediately
   before `azd up`, `azd deploy`, `az deployment ... create`,
   `az group create`, image updates, or any `az ... delete`. The
   assertion is the second guard — it does **not** replace rule 1.
3. **Never `az account set` without `AZURE_CONFIG_DIR` set first.**
   Without isolation, you mutate the global default subscription that
   every other shell on the machine reads.
4. **Never `az login` without `--tenant <id>`.** A bare `az login` opens
   the browser picker and may pick the wrong tenant — silently. Always
   pass `--tenant <id>`. Same goes for `azd auth login --tenant-id <id>`.
   **AND**: `azd` has its own auth chain — `az login` alone does NOT
   satisfy `azd ai agent show` / `azd deploy`, even with `AZD_CONFIG_DIR`
   set. Run **both** logins per shell:

   ```bash
   az login --tenant "$TENANT_ID"
   az account set --subscription "$DEFAULT_SUB"   # MANDATORY for multi-sub tenants — see rule 4a
   azd auth login --tenant-id "$TENANT_ID"
   ```

4a. **Multi-sub tenants: `az login --tenant <id>` defaults to whichever
    sub was last touched, NOT to `default_subscription`.** When a single
    tenant covers multiple subscriptions (e.g., `fruocco-1` and
    `fruocco-2`), `az login --tenant <id>` populates the token cache
    with all of them and silently leaves the active subscription on
    whatever was set last in the global cache. The `default_subscription`
    field in the index file is a **hint to your assertion logic**, not
    a default `az` honors. You MUST run `az account set --subscription
    "$DEFAULT_SUB"` after every `az login` per shell. Mass effect: a
    "deploy to fruocco-1" can land in fruocco-2 if you forget.

    Fast check after login:

    ```bash
    az account show --query "{tenant:tenantId, sub:name}" -o table
    # Verify sub is the one you wanted; if not, az account set --subscription "$DEFAULT_SUB"
    ```

5. **The index file is personal.** It lists your tenant ids. Gitignore
   `~/.azure-tenants/` and `~/.azd-tenants/` globally. Never commit them.
6. **Subprocess inherits env, not isolation state.** Set
   `AZURE_CONFIG_DIR` / `AZD_CONFIG_DIR` in the **parent** before
   spawning anything that calls `az` / `azd` (Python `subprocess`, Node
   `child_process`, `azure.yaml` hooks, GitHub Actions steps, …).
7. **Application code uses `ChainedTokenCredential`, never API keys.**
   Keys bypass the `AZURE_CONFIG_DIR` indirection and break the
   isolation guarantees.

### Agent preflight (Copilot CLI / automated sessions)

Before running **any** `az` / `azd` command in a session:

1. **CHECK** that `AZURE_CONFIG_DIR` (and `AZD_CONFIG_DIR` if `azd` is
   involved) is already set in the current shell.
2. **If NOT set → STOP.** Ask the user which alias from the index this
   session targets. Do not guess. Do not fall back to `~/.azure`.
3. **If set → verify** with `az account show --query tenantId -o tsv`
   that the live context matches the expected alias's tenant id from
   the index.
4. Only then proceed.

### Tenant index = single source of truth

Rule 1 above requires per-tenant `AZURE_CONFIG_DIR` / `AZD_CONFIG_DIR`.
The next section describes the JSON index file that holds the
alias→tenant_id+subscription mapping these env vars are derived from.

---

## The tenant index file

Instead of hard-coding tenant ids in shells, scripts, or docs, keep a small
JSON file describing every tenant you work with. By default it lives at:

- `$env:AZURE_TENANT_INDEX` if set
- otherwise `~/.azure-tenants/index.json`

This file is **personal data** — it lists the tenant ids you work with and
their friendly aliases. **Gitignore it. Never commit it.** A starter copy
lives in [`references/index.example.json`](references/index.example.json).

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
      "azd_config_dir": null,
      "default_subscription": "acme-prod",
      "allowed_subscriptions": ["acme-prod"]
    },
    "dev": {
      "tenant_id": "00000000-0000-0000-0000-000000000002",
      "description": "Development tenant",
      "config_dir": null,
      "azd_config_dir": null,
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
| `tenants.<alias>.config_dir` | string\|null | Override for `AZURE_CONFIG_DIR` (used by `az`). `null` → derive `~/.azure-tenants/<alias>`. **`~` is NOT expanded automatically by JSON readers — consumers must expand it themselves** (see "How to read values from the index" below). |
| `tenants.<alias>.azd_config_dir` | string\|null | Override for `AZD_CONFIG_DIR` (used by `azd`). `null` → derive `~/.azd-tenants/<alias>`. Same `~`-expansion caveat as `config_dir`. **Keep this in lock-step with `config_dir`** — overriding one without the other splits the alias's two halves into different folders, which is almost never what you want. |
| `tenants.<alias>.default_subscription` | string | Subscription name (or id) passed to `az account set` after login. |
| `tenants.<alias>.allowed_subscriptions` | string[] | Whitelist for the strict assertion (membership test — see "Assertion variants" below). Empty/missing → only `default_subscription` is accepted. |

### Bootstrap — manual, no scripts

Unix:

```bash
mkdir -p ~/.azure-tenants ~/.azd-tenants
curl -fsSL -o ~/.azure-tenants/index.json \
  https://raw.githubusercontent.com/aiappsgbb/awesome-gbb/main/skills/azure-tenant-isolation/references/index.example.json
$EDITOR ~/.azure-tenants/index.json   # replace placeholder GUIDs / sub names
```

Windows (PowerShell):

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.azure-tenants" | Out-Null
New-Item -ItemType Directory -Force "$env:USERPROFILE\.azd-tenants"   | Out-Null
Invoke-WebRequest `
  -Uri 'https://raw.githubusercontent.com/aiappsgbb/awesome-gbb/main/skills/azure-tenant-isolation/references/index.example.json' `
  -OutFile "$env:USERPROFILE\.azure-tenants\index.json"
notepad "$env:USERPROFILE\.azure-tenants\index.json"
```

Both `~/.azure-tenants/<alias>/` and `~/.azd-tenants/<alias>/` are created
on demand the first time you `az login` / `azd auth login` against them, so
you don't have to pre-create per-alias subfolders. The two top-level
folders above just hold the index file and serve as the parent for those
auto-created per-alias dirs.

Make sure your global `.gitignore_global` (or repo-level `.gitignore`)
excludes both `.azure-tenants/` and `.azd-tenants/` so the files (and
tokens!) never land in a repo.

---

## Canonical `az` CLI flow

All commands below are bare `az` invocations. The only shell-specific lines
are the env-var exports (which cannot be wrapped).

### How to read values from the index

The skill ships **no wrapper scripts**, but reading values out of a JSON
file is a pure read — not a wrapper — and it's needed every time you set
up a shell. Use the platform's built-in JSON reader:

Unix (Python is already a hard dependency of `az` CLI, so no extra install):

```bash
ALIAS=prod
INDEX="${AZURE_TENANT_INDEX:-$HOME/.azure-tenants/index.json}"

# Extract values (config_dir + azd_config_dir are both nullable -> derive on null)
TENANT_ID=$(python -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); print(d['tenants']['$ALIAS']['tenant_id'])")
DEFAULT_SUB=$(python -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); print(d['tenants']['$ALIAS']['default_subscription'])")
AZ_CFG=$(python  -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); v=d['tenants']['$ALIAS'].get('config_dir');     print(os.path.expanduser(v) if v else os.path.expanduser('~/.azure-tenants/$ALIAS'))")
AZD_CFG=$(python -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); v=d['tenants']['$ALIAS'].get('azd_config_dir'); print(os.path.expanduser(v) if v else os.path.expanduser('~/.azd-tenants/$ALIAS'))")

echo "Tenant: $TENANT_ID  Sub: $DEFAULT_SUB"
echo "AZURE_CONFIG_DIR: $AZ_CFG"
echo "AZD_CONFIG_DIR:   $AZD_CFG"
```

Windows (PowerShell has `ConvertFrom-Json` built-in):

```powershell
$alias = 'prod'
$indexPath = if ($env:AZURE_TENANT_INDEX) { $env:AZURE_TENANT_INDEX } else { "$env:USERPROFILE\.azure-tenants\index.json" }
$idx = Get-Content $indexPath -Raw | ConvertFrom-Json
$t   = $idx.tenants.$alias

$tenantId   = $t.tenant_id
$defaultSub = $t.default_subscription
$configDir = if ($t.config_dir) {
    $t.config_dir -replace '^~', $env:USERPROFILE
} else {
    "$env:USERPROFILE\.azure-tenants\$alias"
}
$azdConfigDir = if ($t.azd_config_dir) {
    $t.azd_config_dir -replace '^~', $env:USERPROFILE
} else {
    "$env:USERPROFILE\.azd-tenants\$alias"
}

"Tenant: $tenantId  Sub: $defaultSub"
"AZURE_CONFIG_DIR: $configDir"
"AZD_CONFIG_DIR:   $azdConfigDir"
```

> **`~` is not auto-expanded.** JSON values are plain strings; both shells
> need an explicit expansion step (`os.path.expanduser` in Python,
> `-replace '^~', $env:USERPROFILE` in PowerShell). The snippets above do
> it for both `config_dir` and `azd_config_dir`.

> **Always extract both paths together.** Setting only `AZURE_CONFIG_DIR`
> from the index while letting `AZD_CONFIG_DIR` fall back to its default
> is a silent split — `az` ends up isolated, `azd` ends up in the global
> `~/.azd`. The snippets above do both in lock-step; if you copy them,
> keep them paired.

#### List all aliases in the index

Useful when you've forgotten what's configured:

```bash
python -c "import json,os; d=json.load(open(os.path.expanduser('${AZURE_TENANT_INDEX:-~/.azure-tenants/index.json}'))); [print(f\"{a:12} {t['tenant_id']}  {t['default_subscription']}\") for a,t in d['tenants'].items()]"
```

```powershell
$indexPath = if ($env:AZURE_TENANT_INDEX) { $env:AZURE_TENANT_INDEX } else { "$env:USERPROFILE\.azure-tenants\index.json" }
(Get-Content $indexPath -Raw | ConvertFrom-Json).tenants.PSObject.Properties |
  ForEach-Object { '{0,-12} {1}  {2}' -f $_.Name, $_.Value.tenant_id, $_.Value.default_subscription }
```

### One-time tenant setup

After running the **How to read values from the index** snippet above for
your alias (so `$TENANT_ID`, `$DEFAULT_SUB`, `$AZ_CFG`, `$AZD_CFG` are
populated), run:

Unix:

```bash
mkdir -p "$AZ_CFG" "$AZD_CFG"
export AZURE_CONFIG_DIR="$AZ_CFG"
export AZD_CONFIG_DIR="$AZD_CFG"
az login --tenant "$TENANT_ID"
az account set --subscription "$DEFAULT_SUB"
az account show
```

Windows:

```powershell
New-Item -ItemType Directory -Force $configDir    | Out-Null
New-Item -ItemType Directory -Force $azdConfigDir | Out-Null
$env:AZURE_CONFIG_DIR = $configDir
$env:AZD_CONFIG_DIR   = $azdConfigDir
az login --tenant $tenantId
az account set --subscription $defaultSub
az account show
```

### Switching tenants in a new shell

If you've already run the one-time setup for that alias before, you don't
need to re-run `az login` — just point the env vars and `az` will pick up
the cached token. Run the **How to read** snippet for the target alias,
then:

Unix:

```bash
export AZURE_CONFIG_DIR="$AZ_CFG"
export AZD_CONFIG_DIR="$AZD_CFG"
az account show --query "{tenantId:tenantId, sub:name}" -o table
```

Windows:

```powershell
$env:AZURE_CONFIG_DIR = $configDir
$env:AZD_CONFIG_DIR   = $azdConfigDir
az account show --query "{tenantId:tenantId, sub:name}" -o table
```

> **First-time use of a config dir:** `az account show` will fail with
> `Please run 'az login' to setup account.` That just means this config
> dir has never been authenticated yet — go back to the **One-time tenant
> setup** flow above (run `az login --tenant <id>` then `az account set
> --subscription <name>`). It is **not** a leaked-tenant problem.

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
export AZURE_CONFIG_DIR="$AZ_CFG"
export AZD_CONFIG_DIR="$AZD_CFG"
az account set --subscription "$DEFAULT_SUB"
[ "$(az account show --query name -o tsv)" = "$DEFAULT_SUB" ] || exit 1
azd up
```

### Assertion variants — strict vs whitelist

The simple snippet above checks against a **single expected subscription**
(typically the alias's `default_subscription`). When an alias legitimately
covers more than one subscription (`allowed_subscriptions` has multiple
entries), use the membership variant instead:

Unix:

```bash
EXPECTED_TENANT=00000000-0000-0000-0000-000000000001
ALLOWED_SUBS=("acme-dev" "acme-test")     # from index.tenants.<alias>.allowed_subscriptions

ACTUAL_TENANT=$(az account show --query tenantId -o tsv)
ACTUAL_SUB=$(az account show --query name -o tsv)

[ "$ACTUAL_TENANT" = "$EXPECTED_TENANT" ] || { echo "❌ Tenant mismatch"; exit 1; }
printf '%s\n' "${ALLOWED_SUBS[@]}" | grep -qx "$ACTUAL_SUB" \
  || { echo "❌ Sub '$ACTUAL_SUB' not in allowed list: ${ALLOWED_SUBS[*]}"; exit 1; }
```

Windows:

```powershell
$expectedTenant = '00000000-0000-0000-0000-000000000002'
$allowedSubs    = @('acme-dev','acme-test')   # from index.tenants.<alias>.allowed_subscriptions

$actualTenant = az account show --query tenantId -o tsv
$actualSub    = az account show --query name     -o tsv

if ($actualTenant -ne $expectedTenant) { Write-Error "Tenant mismatch"; exit 1 }
if ($allowedSubs -notcontains $actualSub) { Write-Error "Sub '$actualSub' not in allowed list: $($allowedSubs -join ', ')"; exit 1 }
```

Pick the strict (single-value) form for production and the whitelist form
when an alias spans multiple subs (e.g. `dev` covers both `acme-dev` and
`acme-test`).

---

## AZD specifics

`azd` reads its own config from `AZD_CONFIG_DIR`, but it picks up the Azure
identity from `AZURE_CONFIG_DIR` (via the same `AzureCliCredential` chain).
Always set both, in lock-step with the alias.

Unix:

```bash
export AZURE_CONFIG_DIR="$AZ_CFG"
export AZD_CONFIG_DIR="$AZD_CFG"
azd auth login --tenant-id "$TENANT_ID"
azd env new prod-env      # first time only
azd env select prod-env   # subsequent runs
azd up
```

Windows:

```powershell
$env:AZURE_CONFIG_DIR = $configDir
$env:AZD_CONFIG_DIR   = $azdConfigDir
azd auth login --tenant-id $tenantId
azd env new prod-env      # first time only
azd env select prod-env   # subsequent runs
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
export AZURE_CONFIG_DIR="$AZ_CFG"
[ "$(az account show --query name -o tsv)" = "$DEFAULT_SUB" ] || exit 1
az deployment group create \
  --resource-group rg-acme \
  --template-file infra/main.bicep \
  --parameters infra/main.parameters.json
```

```powershell
$env:AZURE_CONFIG_DIR = $configDir
if ((az account show --query name -o tsv) -ne $defaultSub) { exit 1 }
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

✅ Right (after running the **How to read** snippet so `$tenantId`,
`$defaultSub`, `$configDir`, `$azdConfigDir` are populated):

```powershell
$env:AZURE_CONFIG_DIR = $configDir
$env:AZD_CONFIG_DIR   = $azdConfigDir
if ((az account show --query name -o tsv) -ne $defaultSub) { exit 1 }
.\infra\scripts\publish_aca.ps1 -RG rg-acme -APP_NAME my-app
```

The same applies to `subprocess.run(["az", ...])` in Python, `child_process`
in Node, hooks in `azure.yaml`, GitHub Actions steps, etc. **Set the env
vars in the parent before invoking the child.**

> **Never use `az account set` to "fix" a wrong-subscription problem
> without first setting `AZURE_CONFIG_DIR`.** Without isolation, you have
> just changed the global default subscription for every other shell.

### Script preamble template

Drop this header at the top of every shell script that touches Azure.
It's the canonical "load alias from index → export both env vars →
verify" sequence in copy-pasteable form. Set `ALIAS=` to the alias the
script targets.

Bash (`# ── Azure Tenant Isolation (REQUIRED) ──`):

```bash
#!/usr/bin/env bash
set -euo pipefail

# ── Azure Tenant Isolation (REQUIRED) ─────────────────────────────────
ALIAS="${AZURE_TENANT_ALIAS:-prod}"   # override at the call site
INDEX="${AZURE_TENANT_INDEX:-$HOME/.azure-tenants/index.json}"

TENANT_ID=$(python -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); print(d['tenants']['$ALIAS']['tenant_id'])")
DEFAULT_SUB=$(python -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); print(d['tenants']['$ALIAS']['default_subscription'])")
AZ_CFG=$(python  -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); v=d['tenants']['$ALIAS'].get('config_dir');     print(os.path.expanduser(v) if v else os.path.expanduser('~/.azure-tenants/$ALIAS'))")
AZD_CFG=$(python -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); v=d['tenants']['$ALIAS'].get('azd_config_dir'); print(os.path.expanduser(v) if v else os.path.expanduser('~/.azd-tenants/$ALIAS'))")

export AZURE_CONFIG_DIR="$AZ_CFG"
export AZD_CONFIG_DIR="$AZD_CFG"

ACTUAL_TENANT=$(az account show --query tenantId -o tsv)
ACTUAL_SUB=$(az account show --query name -o tsv)
[ "$ACTUAL_TENANT" = "$TENANT_ID"   ] || { echo "❌ Tenant mismatch (got $ACTUAL_TENANT, want $TENANT_ID)"; exit 1; }
[ "$ACTUAL_SUB"    = "$DEFAULT_SUB" ] || { echo "❌ Sub mismatch (got $ACTUAL_SUB, want $DEFAULT_SUB)";    exit 1; }
# ─────────────────────────────────────────────────────────────────────

# ... rest of the script ...
```

PowerShell (`# ── Azure Tenant Isolation (REQUIRED) ──`):

```powershell
#requires -Version 7
$ErrorActionPreference = 'Stop'

# ── Azure Tenant Isolation (REQUIRED) ─────────────────────────────────
$alias = if ($env:AZURE_TENANT_ALIAS) { $env:AZURE_TENANT_ALIAS } else { 'prod' }
$indexPath = if ($env:AZURE_TENANT_INDEX) { $env:AZURE_TENANT_INDEX } else { "$env:USERPROFILE\.azure-tenants\index.json" }

$idx = Get-Content $indexPath -Raw | ConvertFrom-Json
$t   = $idx.tenants.$alias
if (-not $t) { throw "Alias '$alias' not found in $indexPath" }

$tenantId   = $t.tenant_id
$defaultSub = $t.default_subscription
$configDir    = if ($t.config_dir)     { $t.config_dir     -replace '^~', $env:USERPROFILE } else { "$env:USERPROFILE\.azure-tenants\$alias" }
$azdConfigDir = if ($t.azd_config_dir) { $t.azd_config_dir -replace '^~', $env:USERPROFILE } else { "$env:USERPROFILE\.azd-tenants\$alias"   }

$env:AZURE_CONFIG_DIR = $configDir
$env:AZD_CONFIG_DIR   = $azdConfigDir

$actualTenant = az account show --query tenantId -o tsv
$actualSub    = az account show --query name     -o tsv
if ($actualTenant -ne $tenantId)   { throw "Tenant mismatch (got $actualTenant, want $tenantId)" }
if ($actualSub    -ne $defaultSub) { throw "Sub mismatch (got $actualSub, want $defaultSub)"     }
# ─────────────────────────────────────────────────────────────────────

# ... rest of the script ...
```

Call site sets the alias once: `AZURE_TENANT_ALIAS=dev ./deploy.sh`
or `$env:AZURE_TENANT_ALIAS='dev'; .\deploy.ps1`. The script is
otherwise alias-agnostic.

---

## Troubleshooting

| Symptom | Diagnose with `az` | Fix |
|---------|-----|-----|
| `az account show` returns wrong tenant | `az account show --query tenantId -o tsv` | Set `AZURE_CONFIG_DIR` to the right alias dir, then `az login --tenant <id>` |
| `azd up` deploys to wrong subscription | `azd env get-values \| grep AZURE_SUBSCRIPTION_ID` and `az account show --query id -o tsv` | Set both `AZURE_CONFIG_DIR` and `AZD_CONFIG_DIR`; `az account set --subscription <name>`; `azd env refresh` |
| `AADSTS50020` / `AADSTS700016` | `az account show --query tenantId` | Token from tenant A used against tenant B. Re-isolate: `rm -rf $AZURE_CONFIG_DIR; mkdir -p $AZURE_CONFIG_DIR; az login --tenant <id>` |
| `az login` opens browser unexpectedly | n/a | Always pass `--tenant <id>` so `az` skips the picker |
| Subscription not found | `az account list --query "[].{name:name,tenantId:tenantId}" -o table` | You're logged into the wrong tenant — `az login --tenant <id>` after setting `AZURE_CONFIG_DIR` |
| Active sub silently wrong after `az login --tenant <id>` (multi-sub tenant) | `az account show --query name -o tsv` after login (returns last-touched sub, not your alias's `default_subscription`) | `az login --tenant <id>` does not honor the index file's `default_subscription` — it just populates the cache. You MUST follow it with `az account set --subscription "$DEFAULT_SUB"`. Bake both into your shell startup script. |
| `azd ai agent show` returns "not logged in" even though `az account show` works | `azd auth login --check-status` (returns "not logged in to Azure") | `azd` uses `AzureDeveloperCliCredential` with its own token cache under `$AZD_CONFIG_DIR/auth/`. Run `azd auth login --tenant-id <id>` separately — `az login` does NOT populate it, even with both env vars set. |
| Multiple terminals interfering | `echo $AZURE_CONFIG_DIR` in each | Every terminal must set its own `AZURE_CONFIG_DIR` before any `az` command |
| `azd auth` token expired | `azd auth login --check-status` | `azd auth login --tenant-id <id>` (with `AZD_CONFIG_DIR` set) |
| Subprocess uses wrong tenant | `az account show` from inside the subprocess | Re-export `AZURE_CONFIG_DIR` and `AZD_CONFIG_DIR` in the parent before spawning |
| Assertion passes but deploy still wrong | `az account show --query "{sub:name, tenant:tenantId}" -o table` immediately before the deploy | Some other process changed `az account set` between assertion and deploy. Tighten by re-running the assertion immediately before each destructive call |
| `az rest --headers ...` fails with "non atteso"/"unexpected" on Windows PowerShell | The `--headers key=value` flag has inconsistent parsing across `az` CLI versions and locales (notably non-EN-US PowerShell hosts) | For app-reg redirect-URI updates use `az ad app update --id <appId> --web-redirect-uris uri1 uri2 …` (replaces the array — read existing first, merge, then update). For other Graph PATCHes, build the body in Python or `Invoke-RestMethod` with a token from `az account get-access-token --resource https://graph.microsoft.com` |
| `az ad app credential reset` wiped every secret on the app reg | Default behaviour is REPLACE, not APPEND — every other ACA app sharing the app reg breaks | Always pass `--append --display-name <label>` and verify with `az ad app credential list --id <appId>` after. For shared app regs (e.g. one Easy Auth identity for many demo containers), the `--display-name` is the only way to tell secrets apart later |

---

## Checklist

For a new terminal, new script, or a fresh agent session:

- [ ] `AZURE_CONFIG_DIR` is set to the tenant-specific directory.
- [ ] `AZD_CONFIG_DIR` is set if `azd` is involved.
- [ ] Logged in via `az login --tenant <id>` **AND** `azd auth login --tenant-id <id>` (separate token caches — `azd` does NOT inherit `az`'s session). Never bare `az login`.
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

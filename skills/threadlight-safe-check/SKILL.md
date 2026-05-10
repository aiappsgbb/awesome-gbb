---
name: threadlight-safe-check
description: >
  Mandatory completeness gate for threadlight pilots — three lifecycle checks
  (post-design, pre-deploy, post-deploy) consolidated into a single CLI.
  Reads SPEC § 11c selectors via specs/manifest.json `deployment_manifest`
  and asserts the spec contract holds end-to-end: design has machine-readable
  manifest, code has every service per `module_selectors`, deployed resource
  group contains every selector's `Microsoft.*` types, every channel reaches.
  USE FOR: completeness gate, deploy gate, safe check, post-deploy gate,
  pre-deploy check, design check, manifest drift, orphan modules, partial
  PoC, missing bot, missing workspace, missing aca-job, deployment_manifest,
  Phase 3.5, postdeploy-manifest.json, threadlight gates.
  DO NOT USE FOR: invocation/runtime tests (use foundry-evals), agent quality
  scoring (use foundry-evals), one-shot azd up commands (use threadlight-deploy
  end-to-end), schema authoring (use threadlight-design).
---

# Threadlight Safe Check — three lifecycle gates, one CLI

The single mandatory completeness gate for any threadlight pilot. Replaces
ad-hoc Phase 3 / Phase 3.5 checks scattered through `threadlight-deploy`
with one consolidated CLI you invoke at three lifecycle points:

```
post-design  → SPEC <-> manifest.json deployment_manifest contract
pre-deploy   → manifest <-> azure.yaml services <-> infra/main.bicep <-> src/<dir>/
post-deploy  → manifest <-> az resource list <-> channel reachability
```

> **Why this skill exists.** The `card-dispute-investigation` v3 PoC
> shipped with **`aca-bot: yes`, `aca-job: yes`, `workspace-ui: yes`**
> in SPEC § 11c — and zero bot resources, zero jobs, zero workspace ACAs
> in the deployed resource group. `azd up` returned 0. Eval scores
> looked plausible. The gap was caught by the user opening the Azure
> Portal and noticing missing tiles. **A consolidated, mandatory gate
> would have caught this in 30 seconds.** That gate is this skill.

## What this skill does NOT replace

- **Invocation testing** of the agent → use `foundry-evals`
- **Authoring** the manifest → use `threadlight-design` (its
  `deployment_manifest{}` JSON block in `specs/manifest.json` is the
  contract this skill consumes)
- **Running `azd up`** → use `threadlight-deploy`. This skill is
  invoked **before** and **after** `azd up`, never instead of.

## When to invoke

| Lifecycle point | Phase | What's checked | Gate result |
|---|---|---|---|
| After SPEC + AGENTS.md drafted | `--phase design` | `specs/manifest.json` contains `deployment_manifest{}`; SPEC § 11c rows match `module_selectors` keys | Drift / fail |
| Before `azd up` | `--phase pre-deploy` | Every `yes` selector → wired in `azure.yaml` + `infra/main.bicep` + has `src/<dir>/Dockerfile`; no orphan Bicep / src folders | Fail-fast |
| After `azd up` returns 0 | `--phase post-deploy` | Every `expected_resource_types` entry in `az resource list`; required ACA roles by name pattern; all `channels` reach HTTP/JWT-OK; `scheduled_jobs` cron correct | **The non-negotiable gate.** Empty `gaps[]` = PoC complete |

Each phase emits a JSON manifest under `tests/` so the gate is auditable
and re-readable later (CI, demo prep, postmortem):

- `tests/safe-check-design-manifest.json`
- `tests/safe-check-predeploy-manifest.json`
- `tests/postdeploy-manifest.json` *(name preserved for backwards-compat with
  the prior `threadlight-deploy` Phase 3.5 manifest)*

All three manifests have a top-level `"gaps": []`. **Empty array = pass.**

---

## CLI

```bash
# From repo root
python -m threadlight.safe_check --phase design        # after threadlight-design Phase 1-3
python -m threadlight.safe_check --phase pre-deploy    # immediately before azd up
python -m threadlight.safe_check --phase post-deploy   # immediately after azd up returns 0
```

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Gate passed (gaps empty) |
| `1` | Gate failed (gaps non-empty); manifest written with details |
| `2` | Missing prerequisite (no `specs/manifest.json`, no `deployment_manifest{}` block, env vars missing) |
| `3` | Tooling error (Azure auth, `az` not on PATH, etc.) |

Optional flags:

```bash
--rg <name>           # override AZURE_RESOURCE_GROUP env var (post-deploy)
--manifest <path>     # override default specs/manifest.json
--out <dir>           # override default tests/ output dir
--strict              # fail on warnings (default: warnings printed, exit 0 if no errors)
--quiet               # only print final OK / FAIL line + exit code
```

---

## Files in this skill

```
threadlight-safe-check/
├── SKILL.md                       (this file)
└── scripts/
    └── safe_check.py              (single-file Python module — the CLI)
```

The CLI is **one file** (~250 LOC) intentionally — copy it into the pilot
repo as `tests/safe_check.py` (or symlink / install as a package) and
invoke. No external dependencies beyond stdlib + `azure-identity` (for
`AzureCliCredential`-honored `az` calls already required by everything
else in the toolchain).

---

## Phase 1 — `--phase design` (post-design check)

**Inputs:** `specs/SPEC.md`, `specs/manifest.json`

**Asserts:**

1. `specs/manifest.json` exists and parses as JSON.
2. Top-level `deployment_manifest{}` block present (added by
   `threadlight-design` Phase 3 — see `threadlight-design/SKILL.md`
   §3 for the schema).
3. `deployment_manifest.module_selectors` is a `dict[str, "yes"|"no"]`
   covering every selector named in SPEC § 11c table.
4. `deployment_manifest.services[]` lists every service that needs a
   container image; every entry has `name`, `host`, `src`.
5. `deployment_manifest.scheduled_jobs[]` listed iff `aca-job: yes`.
6. `deployment_manifest.channels[]` lists every Human Interaction
   channel from SPEC § 8.
7. `deployment_manifest.expected_resource_types[]` non-empty and
   contains the canonical `Microsoft.*` type for every `yes` selector
   per the table in **Selector → resource type map** below.

**Common gaps caught:**

- SPEC § 11c says `aca-bot: yes` but `module_selectors` doesn't list it
  (drift between SPEC text and manifest contract)
- `services[]` references `src/workspace` but SPEC § 8 has no UI
  channel (orphan service)
- `expected_resource_types[]` missing `Microsoft.BotService/botServices`
  even though `aca-bot: yes` (selector mapping incomplete)

---

## Phase 2 — `--phase pre-deploy` (pre-`azd up` check)

**Inputs:** `specs/manifest.json`, `azure.yaml`, `infra/main.bicep`,
`infra/**/*.bicep`, `src/**/Dockerfile`

**Asserts:** Three-column matrix per `yes` selector — every column
populated:

| Selector | `azure.yaml` services | `infra/main.bicep` module ref | `src/<dir>/` Dockerfile |
|---|---|---|---|
| `aca-mcp` | `name: mcp`, `host: containerapp`, `project: ./src/mcp` | `module mcpApp '...container-app.bicep'` with `serviceName: 'mcp'` | `src/mcp/Dockerfile` + `server.py` |
| `aca-bot` | `name: bot`, `host: containerapp`, `project: ./src/bot` | `module botApp '...container-app.bicep'` with `serviceName: 'bot'` **AND** `module botService 'bot/bot-service.bicep'` | `src/bot/Dockerfile` + `bot.py` + `app.py` + `teams_package/manifest.json` |
| `aca-job` | `name: <job>`, `host: containerapp`, `project: ./src/jobs/<job>` | `module job 'jobs/aca-job.bicep'` (or equivalent under `infra/jobs/`) | `src/jobs/<job>/Dockerfile` + `main.py` (cron entrypoint) |
| `workspace-ui` | `name: workspace`, `host: containerapp`, `project: ./src/workspace` | `module workspaceApp '...container-app.bicep'` with `serviceName: 'workspace'` | `src/workspace/Dockerfile` + ACA-served HTML/SPA. **NOT a static `index.html` only.** |
| `foundry-iq-index` | n/a (provisioned by hook) | `module knowledge 'modules/ai-search.bicep'` (the index) | `scripts/postprovision.py` calls `provision_knowledge_base()` |

Plus **two orphan checks** (caught the card-dispute v3 ghost
`infra/bot/aca.bicep` for an entire deploy cycle):

1. **Bicep-module orphan check.** Every `infra/<dir>/*.bicep` (excluding
   `core/`, `modules/`) must be referenced from `infra/main.bicep` via
   `module ... '<path>'`. Otherwise → orphan; either wire or delete.
2. **`src/`-folder orphan check.** Every `src/<dir>/` must map to a
   declared `azure.yaml` service (or be `src/agent/` which has its own
   host). Otherwise → orphan; either wire or delete.

**Common gaps caught:**

- `aca-bot: yes` but `azure.yaml` has no `bot` service → silent partial
  PoC
- `infra/bot/aca.bicep` exists but no `module botApp` line in
  `main.bicep` → ghost module that looks deployed in `infra/` listing
  but never lands in Azure
- `src/workspace/index.html` exists but no `src/workspace/Dockerfile`
  → static page treated as "deployed" with nowhere to run

---

## Phase 3 — `--phase post-deploy` (post-`azd up` gate, MANDATORY)

> This is the gate that catches "azd reported success but half the
> SPEC didn't ship".

**Inputs:** `specs/manifest.json`, `AZURE_RESOURCE_GROUP` (env var or
`--rg`), live Azure subscription via `az`/`AzureCliCredential`.

### Step 1 — capture deployed state

```bash
RG="${AZURE_RESOURCE_GROUP:-$(azd env get-value AZURE_RESOURCE_GROUP)}"

az resource list -g "$RG" \
   --query "[].{type:type, name:name}" -o json > tests/deployed-resources.json

az containerapp list -g "$RG" \
   --query "[].{name:name, fqdn:properties.configuration.ingress.fqdn, state:properties.runningStatus}" \
   -o json > tests/deployed-containerapps.json

az containerapp job list -g "$RG" \
   --query "[].{name:name, schedule:properties.configuration.scheduleTriggerConfig.cronExpression}" \
   -o json > tests/deployed-jobs.json

# IMPORTANT: `az bot list` does NOT exist. Use the generic resource API:
az resource list -g "$RG" \
   --resource-type Microsoft.BotService/botServices \
   -o json > tests/deployed-bots.json
```

### Step 2 — diff against `expected_resource_types`

```python
expected_types = set(manifest["deployment_manifest"]["expected_resource_types"])
deployed_types = {r["type"] for r in deployed_resources}
missing_types = expected_types - deployed_types
```

### Step 3 — required-role check (catches "right type wrong name")

For each ACA, assert at least one matches each required role pattern.
This catches "we deployed *some* ACA but it's the MCP again, not the
bot".

```python
required_aca_roles = {"mcp", "bot", "workspace"}   # subset of services per manifest
present_roles = set()
for aca in deployed_acas:
    for role in required_aca_roles:
        if role in aca["name"].lower():
            present_roles.add(role)
unmet = required_aca_roles - present_roles
```

### Step 4 — channel reachability

For every entry in `deployment_manifest.channels[]`:

| Channel `type` | Probe |
|---|---|
| `web` (workspace) | `GET https://<fqdn>/` returns HTTP 200 (and optionally `/health` returns "ok") |
| `teams` (bot) | `POST https://<fqdn>/api/messages` with empty body → expect HTTP 401 with `Authorization header not found` (= JWT middleware live) |
| `email` / `webhook` | n/a (deferred — only logs presence) |

### Step 5 — scheduled-job cron correctness

For every entry in `deployment_manifest.scheduled_jobs[]`:

```python
for job in manifest_jobs:
    matched = next((j for j in deployed_jobs if job["name"] in j["name"]), None)
    if not matched:
        gaps.append(f"missing scheduled job: {job['name']}")
    elif matched["schedule"] != job["schedule"]:
        gaps.append(f"job {job['name']} cron drift: deployed={matched['schedule']} expected={job['schedule']}")
```

### Step 6 — write `tests/postdeploy-manifest.json`

```json
{
  "phase": "post-deploy",
  "deployed_at": "2026-05-10T22:30:00Z",
  "rg": "rg-card-dispute-poc",
  "checked_selectors": ["foundry-account", "cosmos-db", "ai-search", "aca-mcp", "aca-bot", "aca-job", "workspace-ui"],
  "deployed_resource_types": ["Microsoft.CognitiveServices/accounts", "..."],
  "channels": [
    { "name": "Analyst Workspace", "type": "web", "fqdn": "ca-workspace-...azurecontainerapps.io", "status": "OK" },
    { "name": "Teams adaptive card", "type": "teams", "fqdn": "ca-bot-...azurecontainerapps.io", "status": "OK_jwt_alive" }
  ],
  "scheduled_jobs": [
    { "name": "deadline-watcher", "schedule": "*/15 * * * *", "status": "OK" }
  ],
  "gaps": []
}
```

> **`gaps` MUST be empty.** Anything else means: either fix the gap
> (preferred), or update SPEC § 11c **and** the `deployment_manifest`
> in lock-step to flip the selector to `no` with a documented
> rationale ("scheduled job deferred to v2"). **Silently shipping
> with gaps is the failure mode this whole gate exists to prevent.**

---

## Selector → resource type map (canonical)

The `deployment_manifest.expected_resource_types[]` list a
`threadlight-design` author writes is mechanically derived from this
table. Safe-check uses the same table for the post-deploy diff.

| Selector | Expected `Microsoft.*` resource types |
|---|---|
| `foundry-account` | `Microsoft.CognitiveServices/accounts` |
| `cosmos-db` | `Microsoft.DocumentDB/databaseAccounts` |
| `ai-search` | `Microsoft.Search/searchServices` |
| `app-insights` | `Microsoft.Insights/components` + `Microsoft.OperationalInsights/workspaces` |
| `acr` | `Microsoft.ContainerRegistry/registries` |
| `uami` | `Microsoft.ManagedIdentity/userAssignedIdentities` |
| `aca-environment` | `Microsoft.App/managedEnvironments` |
| `aca-mcp` | `Microsoft.App/containerApps` (1+ named `*mcp*`) |
| `aca-bot` | `Microsoft.App/containerApps` (1+ named `*bot*`) **AND** `Microsoft.BotService/botServices` |
| `aca-job` | `Microsoft.App/jobs` (1 per cron entry) |
| `workspace-ui` | `Microsoft.App/containerApps` (1+ named `*workspace*` or `*ui*`) |
| `event-grid` | `Microsoft.EventGrid/topics` (or `systemTopics`) |
| `service-bus` | `Microsoft.ServiceBus/namespaces` |
| `key-vault` | `Microsoft.KeyVault/vaults` (only if explicitly `yes` — keyless-by-default) |
| `storage-blob` | `Microsoft.Storage/storageAccounts` |
| `foundry-iq-index` | `Microsoft.Search/searchServices` (typically same as `ai-search`) |

---

## Windows-specific quirks (BAKED IN)

These are **must-handle** on Windows shells running Azure CLI; they
silently break naive `subprocess.run(["az", ...])` calls. The shipped
`safe_check.py` includes all three workarounds.

### 1. `az` is `az.cmd`, not `az.exe` — needs `shell=True`

`subprocess.run(["az", "resource", "list", ...])` on Windows fails with
`[WinError 2] The system cannot find the file specified` because Python
won't traverse `PATHEXT` for a non-`.exe`. Use:

```python
subprocess.run(["az", "resource", "list", ...], shell=True, capture_output=True, text=True, check=True)
```

`shell=True` lets cmd.exe resolve `az.cmd` from `PATHEXT`. Yes,
shell=True is normally an injection risk — here all args are
hard-coded or come from `azd env get-value` (not user input).

### 2. `az bot list` does NOT exist

The Bot Service CLI exposes `az bot show -n <name> -g <rg>` per
resource, not a list. To enumerate bots in a RG, use the generic
resource API:

```bash
az resource list -g <rg> --resource-type Microsoft.BotService/botServices -o json
```

### 3. `az` honors `AZURE_CONFIG_DIR` only if env vars set in *parent*

The Python process inherits parent env vars, but if `AZURE_CONFIG_DIR`
isn't set in the shell that launches `python -m threadlight.safe_check`,
`az` falls back to `~/.azure` and reads the wrong tenant. Per
`azure-tenant-isolation`: set both `AZURE_CONFIG_DIR` and
`AZD_CONFIG_DIR` in the shell before invoking this gate.

The CLI itself logs the active tenant + subscription as its first line
of output, so any cross-tenant slip is immediately visible.

---

## Bot health-check semantics

A bot ACA returning HTTP 401 with body `{"error": "Authorization header
not found"}` from `POST /api/messages` is the **healthy "alive and
rejecting" state**. The microsoft-agents SDK's
`jwt_authorization_middleware` is correctly enforcing Bot Framework
token validation. `safe_check.py` records this as `"status":
"OK_jwt_alive"`, NOT a gap.

To smoke-test the bot end-to-end, use either:

- the Bot Framework Emulator (local, manual), or
- a Teams sideload via the generated `teams_package/manifest.json`

Both are out of scope for this gate (covered by `foundry-teams-bot`).

---

## Hooking into `azd up`

Add to `azure.yaml`:

```yaml
hooks:
    predeploy:
        shell: pwsh
        run: python -m threadlight.safe_check --phase pre-deploy
    postdeploy:
        shell: pwsh
        run: |
            cd scripts
            uv sync --frozen --quiet
            uv run postdeploy.py     # existing seed script
            cd ..
            python -m threadlight.safe_check --phase post-deploy
```

`predeploy` exits 1 → `azd deploy` aborts before the `docker build`,
saving 5+ minutes of wasted ACR push when a service is missing.

`postdeploy` runs after `azd up` reports success — but before the human
declares "PoC complete". A non-zero exit here is the **single most
important signal** in the threadlight toolchain: it means SPEC said one
thing and Azure shipped another. Don't dismiss it.

---

## Anti-pattern: "the agent runs in the portal so we're done"

The PoC is **NOT done** when:

- Only the hosted agent + 1 MCP ACA are deployed but SPEC § 11c
  declared more (`aca-bot`, `aca-job`, `workspace-ui`).
- The smoke probe / eval invokes the agent successfully but the
  agent's deployed surface area doesn't match SPEC § 8 channels.
- Bicep modules are present in `infra/` but not wired into
  `main.bicep` (orphans).
- Source folders exist under `src/` but aren't declared in
  `azure.yaml` services.
- `tests/postdeploy-manifest.json` doesn't exist or has non-empty
  `gaps[]`.

If any of the above is true, the PoC is **partial**. Communicate that
honestly to the user (with the gap list from `safe-check`) instead of
declaring victory.

---

## Cross-references

- `threadlight-design` — authors the `deployment_manifest{}` block in
  `specs/manifest.json` that this skill consumes
- `threadlight-deploy` — invokes this skill at `predeploy` and
  `postdeploy` hooks; its Phase 3 / Phase 3.5 sections now reference
  this skill as the canonical implementation
- `azure-tenant-isolation` — `AZURE_CONFIG_DIR` setup that
  `safe_check.py` relies on for correct-tenant `az` calls
- `azd-patterns` — module library and canonical Bicep selector
  vocabulary the pre-deploy check uses

## References

- `scripts/safe_check.py` — the single-file CLI implementation

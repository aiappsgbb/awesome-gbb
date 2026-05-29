---
schema_version: 2

freshness_tier: A

# Live ARM provisioning + data-plane call needs an Azure sub we don't
# ship to the coding agent, so refresh is human-driven.
automation_tier: auto

# Primary upstream — Microsoft's official toolchain
upstream:
  type: github_repo
  repo: microsoft/sre-agent
  ref: main
  pinned_sha: a401e003a3874c374f5fff5278123a1f603fe270
  pinned_commit_message: |
    Merge pull request #172 from dm-chelupati/fix/e2e-bugs
  license: MIT
  notes: |
    This skill is a thin GBB wrapper around microsoft/sre-agent. We do NOT
    fork — we vendor recipes and plugins in upstream shape and contribute
    PRs back. SHA drift weekly opens a refresh issue; reviewer compares
    sreagent-templates/recipes/ for new patterns we should mirror or
    deprecate ours against.

# Secondary upstream — official plugin marketplace (tracked manually below
# because the schema currently supports one `upstream` block; check the
# pinned SHA against the value in docs_to_revalidate below)
packages: []

# Documentation URLs (link-rot detector input)
docs_to_revalidate:
  - https://learn.microsoft.com/en-us/azure/sre-agent/overview
  - https://learn.microsoft.com/en-us/azure/sre-agent/create-agent
  - https://learn.microsoft.com/en-us/azure/sre-agent/sub-agents
  - https://learn.microsoft.com/en-us/azure/sre-agent/api-reference
  - https://learn.microsoft.com/en-us/azure/sre-agent/network-requirements
  - https://learn.microsoft.com/en-us/azure/sre-agent/run-modes
  - https://learn.microsoft.com/en-us/azure/sre-agent/skills
  - https://learn.microsoft.com/en-us/azure/sre-agent/scheduled-tasks
  - https://learn.microsoft.com/en-us/azure/templates/microsoft.app/agents
  - https://github.com/microsoft/sre-agent
  - https://github.com/microsoft/sre-agent/tree/main/sreagent-templates
  - https://github.com/Azure/sre-agent-plugins
  - https://github.com/Azure/sre-agent-plugins/tree/main/plugins

known_issues:
  - id: KI-001
    description: Microsoft.App RP not registered on fresh subs → DeploymentNotFound
    upstream_url: https://learn.microsoft.com/en-us/azure/sre-agent/create-agent
    status: open
    workaround_location: SKILL.md § 3 "Known traps" first row

  - id: KI-002
    description: Zscaler / corporate proxy blocks *.azuresre.ai data plane
    upstream_url: https://learn.microsoft.com/en-us/azure/sre-agent/network-requirements
    status: open
    workaround_location: SKILL.md § 3 step 4 + "Known traps" row 4

  - id: KI-003
    description: ARM API still preview (2025-05-01-preview); drift detector should flag GA promotion of Microsoft.App/agents
    upstream_url: https://learn.microsoft.com/en-us/azure/sre-agent/api-reference
    status: open
    workaround_location: SKILL.md § "Cross-references"

  - id: KI-004
    description: SRE Agent chat is English-only at preview; customers asking in other languages get garbage answers
    upstream_url: https://learn.microsoft.com/en-us/azure/sre-agent/overview
    status: open
    workaround_location: SKILL.md § 3 "Known traps" last row

# Machine-runnable validation contract
validation:
  requires:
    - github_only

  runnable: true

  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    # 1. Verify the primary upstream SHA still resolves
    GOT_SHA=$(git ls-remote https://github.com/microsoft/sre-agent main | awk '{print $1}')
    echo "microsoft/sre-agent main HEAD: $GOT_SHA"

    # 2. Verify the plugin marketplace upstream is reachable
    PLUGINS_SHA=$(git ls-remote https://github.com/Azure/sre-agent-plugins main | awk '{print $1}')
    echo "Azure/sre-agent-plugins main HEAD: $PLUGINS_SHA"

    # 3. Verify the byte-exact recipe shape we vendor against still exists
    #    (the upstream minimal recipe — if upstream renames files our recipes break)
    curl -sLf https://raw.githubusercontent.com/microsoft/sre-agent/main/sreagent-templates/recipes/minimal/agent.json > /dev/null
    echo "upstream minimal/agent.json reachable"

    curl -sLf https://raw.githubusercontent.com/Azure/sre-agent-plugins/main/plugins/datadog/plugin.json > /dev/null
    echo "upstream datadog/plugin.json reachable"

  expected_output:
    - "microsoft/sre-agent main HEAD:"
    - "Azure/sre-agent-plugins main HEAD:"
    - "upstream minimal/agent.json reachable"
    - "upstream datadog/plugin.json reachable"

  failure_signatures:
    - "404"
    - "Could not resolve host"

last_validated: 2026-05-20
validated_by: copilot-cli
known_issues_count: 4
---

# Upstream pin — `azure-sre-agent` skill

This file is the **machine-readable validation contract** for the
`azure-sre-agent` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly.

The skill tracks **two** upstream repos. The schema's primary `upstream`
block tracks `microsoft/sre-agent`; the secondary `Azure/sre-agent-plugins`
SHA is captured below and re-validated via the `validation.script` above.

---

## 1. Pinned upstreams

| Field | Primary (`microsoft/sre-agent`) | Secondary (`Azure/sre-agent-plugins`) |
|-------|------------------------------|--------------------------------------|
| **Branch** | `main` | `main` |
| **Pinned SHA** | `a401e003a3874c374f5fff5278123a1f603fe270` | `484e5ca1108d52bbc09fbf90e0f07681a302608a` |
| **Pinned commit subject** | Merge PR #172 fix/e2e-bugs | Add AWS and Azure Managed Grafana plugins (#7) |
| **License** | MIT | MIT |
| **First authored against** | 2026-05-20 | 2026-05-20 |

Refresh procedure:
```bash
git ls-remote https://github.com/microsoft/sre-agent main
git ls-remote https://github.com/Azure/sre-agent-plugins main
```
Compare each first column to the SHAs above. If either drifts more than a
few commits, scan their `recipes/` / `plugins/` directories for new
patterns we should mirror or that obsolete ours.

---

## 2. ARM API pin

- **Control plane preview API**: `2025-05-01-preview` (used by `data_plane.py`)
- **Bicep stable**: `Microsoft.App/agents@2026-01-01`

When `Microsoft.App/agents` reaches GA, the preview API version may
deprecate. Drift detector will flag this via doc revalidation on
`learn.microsoft.com/en-us/azure/sre-agent/api-reference`.

---

## 3. Verification checklist (the executable contract)

```bash
#!/usr/bin/env bash
set -euo pipefail

GOT_SHA=$(git ls-remote https://github.com/microsoft/sre-agent main | awk '{print $1}')
echo "microsoft/sre-agent main HEAD: $GOT_SHA"

PLUGINS_SHA=$(git ls-remote https://github.com/Azure/sre-agent-plugins main | awk '{print $1}')
echo "Azure/sre-agent-plugins main HEAD: $PLUGINS_SHA"

curl -sLf https://raw.githubusercontent.com/microsoft/sre-agent/main/sreagent-templates/recipes/minimal/agent.json > /dev/null
echo "upstream minimal/agent.json reachable"

curl -sLf https://raw.githubusercontent.com/Azure/sre-agent-plugins/main/plugins/datadog/plugin.json > /dev/null
echo "upstream datadog/plugin.json reachable"
```

**Expected output** must contain (substring match):

- `microsoft/sre-agent main HEAD:`
- `Azure/sre-agent-plugins main HEAD:`
- `upstream minimal/agent.json reachable`
- `upstream datadog/plugin.json reachable`

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| `git ls-remote microsoft/sre-agent main` | ✅ | `a401e003a3874c374f5fff5278123a1f603fe270` |
| `git ls-remote Azure/sre-agent-plugins main` | ✅ | `484e5ca1108d52bbc09fbf90e0f07681a302608a` |
| `curl HEAD upstream minimal/agent.json` | ✅ | 200 OK |
| `curl HEAD upstream datadog/plugin.json` | ✅ | 200 OK |

Captured at `last_validated: 2026-05-20` by `copilot-cli`.

---

## 5. Known issues at this pin

### KI-001 — Microsoft.App RP not registered → DeploymentNotFound

**Upstream tracker:** <https://learn.microsoft.com/en-us/azure/sre-agent/create-agent>
**Status:** open

Fresh Azure subscriptions don't have `Microsoft.App` registered. The
SRE Agent wizard then deploys an inner ARM operation that returns
`DeploymentNotFound` with no clear surface error.

**Workaround:**

```bash
az provider register --namespace Microsoft.App --subscription <sub-id>
```

Built into `scripts/preflight.sh` as gate 1.

### KI-002 — Zscaler / corporate proxy blocks `*.azuresre.ai`

**Upstream tracker:** <https://learn.microsoft.com/en-us/azure/sre-agent/network-requirements>
**Status:** open

Many enterprise proxies (Zscaler especially) default-deny wildcard
domains. The SRE Agent data-plane endpoint lives at `*.azuresre.ai`;
without explicit allow-list, chat works in a browser but dies in CLI.

**Workaround:** Add to corporate proxy allow-list (preflight gate 4):

```
*.azuresre.ai
sre.azure.com
```

### KI-003 — ARM API still in preview

**Upstream tracker:** <https://learn.microsoft.com/en-us/azure/sre-agent/api-reference>
**Status:** open

Sub-resource ARM operations use `2025-05-01-preview`. When the API
graduates to GA, our `data_plane.py` should pin to the stable
version. Detector flags via doc-URL revalidation.

### KI-004 — Chat is English-only at preview

**Upstream tracker:** <https://learn.microsoft.com/en-us/azure/sre-agent/overview>
**Status:** open

Documented limitation. Customers asking in other languages get garbage
answers. Communicate at engagement-kickoff; pin chat language to `en-US`.

---

## 6. Re-pin procedure

When upstream advances:

1. Run `git ls-remote https://github.com/microsoft/sre-agent main` and
   `git ls-remote https://github.com/Azure/sre-agent-plugins main`
2. Update front-matter `upstream.pinned_sha` and `upstream.pinned_commit_message`
3. Update § 1 table SHAs
4. Run the `validation.script` (above and front-matter — kept identical)
5. Update `last_validated` and `validated_by`
6. Bump `SKILL.md` `metadata.version` PATCH (per AGENTS.md § 5)
7. Open PR with title `chore(azure-sre-agent): re-pin upstream → <short-sha>`

If a new recipe or plugin lands upstream, evaluate whether ours
duplicates it (deprecate or merge upstream) or whether the new shape
breaks our vendored recipes (update parameter names).

---

## 7. URLs to re-validate (link-rot detector input)

- <https://learn.microsoft.com/en-us/azure/sre-agent/overview>
- <https://learn.microsoft.com/en-us/azure/sre-agent/create-agent>
- <https://learn.microsoft.com/en-us/azure/sre-agent/sub-agents>
- <https://learn.microsoft.com/en-us/azure/sre-agent/api-reference>
- <https://learn.microsoft.com/en-us/azure/sre-agent/network-requirements>
- <https://learn.microsoft.com/en-us/azure/sre-agent/run-modes>
- <https://learn.microsoft.com/en-us/azure/sre-agent/skills>
- <https://learn.microsoft.com/en-us/azure/sre-agent/scheduled-tasks>
- <https://learn.microsoft.com/en-us/azure/templates/microsoft.app/agents>
- <https://github.com/microsoft/sre-agent>
- <https://github.com/microsoft/sre-agent/tree/main/sreagent-templates>
- <https://github.com/Azure/sre-agent-plugins>
- <https://github.com/Azure/sre-agent-plugins/tree/main/plugins>

---

## 8. Cross-references worth bookmarking

- `microsoft/sre-agent/sreagent-templates/recipes/azmon-lawappinsights/` — canonical "full-fat" recipe shape; what our 3 recipes are modeled on
- `microsoft/sre-agent/sreagent-templates/recipes/minimal/` — barest-bones recipe; what our `preflight.sh` references
- `Azure/sre-agent-plugins/plugins/datadog/` — canonical plugin shape with MCP server
- `Azure/sre-agent-plugins/plugins/pager-duty/` — canonical plugin shape, MCP-only

---

## 9. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. The pin file has `automation_tier: auto` — do NOT autonomously
>    PR. Live SRE Agent provisioning needs an Azure sub.
> 2. For SHA-drift issues, re-run `validation.script` (it's runnable
>    without a sub), update SHAs, bump SKILL.md `metadata.version` PATCH,
>    open PR.
> 3. For doc-URL link-rot, find the new URL on learn.microsoft.com and
>    update both the body anchor and `docs_to_revalidate[]`. Do NOT
>    silently delete a doc URL.
> 4. NEVER edit recipes/ or plugins/ contents without `[skill-rewrite]`
>    in the commit message — those are byte-exact mirrors of upstream
>    shape and the automation-pr-gate enforces this.

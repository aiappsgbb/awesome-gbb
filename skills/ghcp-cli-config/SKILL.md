---
name: ghcp-cli-config
description: >
  Bootstrap GitHub Copilot CLI for GBB workflows: 6 recommended MCP servers
  (mslearn, Azure, Playwright, context7, tavily, mem0), settings.json
  baseline (model, sessionSync, allowedUrls, trustedFolders), work-iq
  plugin family for Microsoft staff, autoApprove guardrails, and a
  fresh-machine bootstrap procedure the agent can execute.
  USE FOR: copilot cli setup, fresh machine setup, configure ghcp cli,
  add ms learn mcp, add azure mcp, add playwright mcp, mcp-config.json,
  settings.json, sessionSync, allowedUrls, trustedFolders, autoApprove,
  permissions-config.json, copilot cli plugins, install workiq,
  extraKnownMarketplaces, ghcp first time, copilot cli onboarding,
  recommended copilot cli config, gbb engineer setup.
  DO NOT USE FOR: authoring new skills (use skill-creator), Azure tenant
  isolation (use azure-tenant-isolation), keyboard shortcuts and slash
  commands (runtime, not config), Cursor or Claude Code config (different
  runtimes).
metadata:
  version: "1.0.5"
---

# GHCP CLI Config

Configure GitHub Copilot CLI (the `copilot` command) for the workflows
this catalog assumes — six MCP servers, sane `settings.json` defaults,
the work-iq plugin family for Microsoft staff, sensible `autoApprove`
guardrails, and a fresh-machine bootstrap the agent can run end-to-end.

> **Provenance.** Distilled from the live `~/.copilot/` of an active
> GBB engineer working across Threadlight, Foundry, and Citadel. All
> real API keys have been replaced with `<your-…-key>` placeholders.
> All real folder names in `trustedFolders` have been replaced with
> generic placeholders. The `m-*.json` managed files are deliberately
> NOT documented as user-editable — Copilot CLI rewrites them and your
> edits will be lost.

---

## When to use

Invoke this skill when:

- Setting up Copilot CLI on a **fresh machine** for the first time
- Adding a new MCP server (`add ms learn mcp`, `add azure mcp`, …)
- A teammate asks "what should my `mcp-config.json` look like?"
- You want to enable `sessionSync` to roam sessions across machines
- You need to whitelist `trustedFolders` so the agent stops asking on
  every cd into a working repo
- You're enabling Microsoft staff plugins (work-iq, m365-agents-toolkit)

## When NOT to use

- **Authoring a new skill** → use `skill-creator`
- **Per-tenant Azure isolation** → use `azure-tenant-isolation` (sets
  `AZURE_CONFIG_DIR` per shell — the Azure MCP server below honors it)
- **Cursor / Claude Code / Zed config** → different runtimes, different
  files; this skill only covers GHCP CLI

---

## File map (where everything lives)

```
~/.copilot/
├── settings.json              ← USER-EDITABLE. Top-level prefs (model, sync, trusted folders, plugins).
├── mcp-config.json            ← USER-EDITABLE. MCP server registry.
├── permissions-config.json    ← AUTO-MANAGED. Per-folder "Yes, always" approvals — never edit by hand.
├── m-settings.json            ← MANAGED. Auto-rewritten by the runtime. Do NOT edit.
├── m-mcp-servers.json         ← MANAGED. Auto-rewritten. Do NOT edit.
├── m-preferences.json         ← MANAGED. Do NOT edit.
├── skills/<skill-name>/       ← USER-SCOPE skills (this catalog's recommended install location).
├── installed-plugins/         ← Plugin cache (filled by `copilot plugin install …`).
├── session-state/<session-id>/← Per-session workspace (plan.md, checkpoints, files).
└── session-store.db           ← SQLite cross-session history (queryable).
```

The two files this skill writes are **`settings.json`** and
**`mcp-config.json`**. Everything else is either auto-managed by the
runtime or per-skill / per-session state.

---

## Quick start (5 minutes, no API keys needed)

The minimum viable setup uses the three no-auth MCP servers (`mslearn`,
`Azure`, `Playwright`). Drop this into `~/.copilot/mcp-config.json`:

```json
{
  "mcpServers": {
    "mslearn": {
      "type": "http",
      "url": "https://learn.microsoft.com/api/mcp",
      "tools": ["*"],
      "headers": {}
    },
    "Azure": {
      "type": "local",
      "command": "npx",
      "args": ["-y", "@azure/mcp@latest", "server", "start"],
      "tools": ["*"]
    },
    "Playwright": {
      "type": "local",
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@playwright/mcp@0.0.42", "--isolated", "--headless"],
      "tools": ["*"]
    }
  }
}
```

The full version (with `context7` / `tavily` / `mem0` and placeholder
keys) is in [`references/mcp-config.full.json`](references/mcp-config.full.json).

Restart `copilot` after editing `mcp-config.json`. Verify with `/mcp`
inside the session — the three servers should appear.

> **`cmd /c` on Windows is intentional for Playwright.** `npx.cmd` isn't
> always on PATH the way the runtime expects; wrapping in `cmd /c` makes
> the launch reliable across PowerShell hosts. On macOS / Linux drop the
> `cmd /c` prefix and call `npx` directly.

---

## Recommended MCP servers (the GBB six)

| Server | Type | Auth | Why it's worth installing |
|--------|------|------|--------------------------|
| **mslearn** | HTTP | None | Two tools: `microsoft_docs_search` + `microsoft_docs_fetch`. Pulls authoritative Microsoft docs (Foundry, Azure, M365, .NET) directly into context. Drastically reduces hallucinated API surface. **Highest-ROI of the six.** |
| **Azure** | Local stdio | `az login` | Resource management via natural language ("list my container apps in rg-foo"). Honors `AZURE_CONFIG_DIR` if set per shell — pairs cleanly with `azure-tenant-isolation`. |
| **Playwright** | Local stdio | None | Headless browser automation, screenshots, page extraction, demo recording. The `--isolated` flag uses an ephemeral profile (no cookie leakage between sessions). |
| **context7** | HTTP | API key | Library docs lookup (`resolve-library-id` → `get-library-docs`). Best for "what's the latest API of `@azure/identity`?" without web-fetching. Free tier sufficient for normal use. |
| **tavily** | HTTP | API key | Web search alternative to fetch — better for "find articles about X" style queries that need ranked results. Free tier sufficient. |
| **mem0** | Local stdio (Python) | API key | Long-term memory across sessions (separate from per-session `m_remember` and the SQL `session-store.db`). Useful for personal preferences that should follow you across all repos. |

### Per-server snippets

#### mslearn (no auth)

```json
"mslearn": {
  "type": "http",
  "url": "https://learn.microsoft.com/api/mcp",
  "tools": ["*"],
  "headers": {}
}
```

When working on Foundry / Azure / M365, **invoke `mslearn` BEFORE
falling back to web fetches**. The signal-to-noise is higher and the
agent gets the canonical doc URL for citation.

#### Azure (no auth — uses `az login` token cache)

```json
"Azure": {
  "type": "local",
  "command": "npx",
  "args": ["-y", "@azure/mcp@latest", "server", "start"],
  "tools": ["*"]
}
```

This server reads the same token cache as `az` CLI. **If you use
`AZURE_CONFIG_DIR` per terminal (per `azure-tenant-isolation`), the
Copilot CLI process must inherit that env var** — set it before
launching `copilot`, not inside the session.

#### Playwright (no auth, headless + isolated)

```json
"Playwright": {
  "type": "local",
  "command": "cmd",
  "args": ["/c", "npx", "-y", "@playwright/mcp@0.0.42", "--isolated", "--headless"],
  "tools": ["*"]
}
```

`--isolated` = ephemeral browser profile per session (no cookies kept).
`--headless` = no visible browser window. Drop both flags if you want
to watch the agent click through.

#### context7 (API key required)

```json
"context7": {
  "type": "http",
  "url": "https://mcp.context7.com/mcp",
  "tools": ["*"],
  "headers": { "CONTEXT7_API_KEY": "<your-context7-api-key>" }
}
```

Get a free key at <https://context7.com/>. Use it when the agent needs
library API surface that isn't well-covered by `mslearn` (anything
non-Microsoft: `react-query`, `playwright-python`, `pandas`, etc.).

#### tavily (API key required)

```json
"tavily": {
  "type": "http",
  "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=<your-tavily-api-key>",
  "tools": ["*"],
  "headers": {}
}
```

Free key at <https://tavily.com/>. Two tools: `tavily_search` (ranked
results) and `tavily_extract` (full-page extraction with cleanup).

#### mem0 (API key + Python install required)

```json
"mem0": {
  "type": "local",
  "command": "python",
  "args": ["-m", "mem0_mcp_server.server"],
  "tools": ["*"],
  "env": {
    "MEM0_API_KEY": "<your-mem0-api-key>",
    "MEM0_DEFAULT_USER_ID": "default"
  }
}
```

Install once: `pip install mem0-mcp-server`. Free key at <https://mem0.ai/>.
Use sparingly — broad memory across all sessions can leak project context
between unrelated work. The built-in `m_remember` / SQL `session-store.db`
covers most needs.

---

## `settings.json` baseline

Live at `~/.copilot/settings.json`. The keys most worth setting:

```json
{
  "model": "claude-opus-4.7",
  "renderMarkdown": true,
  "showReasoning": false,

  "allowedUrls": [
    "https://raw.githubusercontent.com",
    "https://docs.github.com"
  ],

  "sessionSync": [
    { "origin": "*", "level": "user" }
  ],

  "trustedFolders": [
    "<absolute-path-to-your-repos-root>",
    "<absolute-path-to-another-trusted-folder>"
  ],

  "extraKnownMarketplaces": {
    "copilot-plugins": {
      "source": { "source": "github", "repo": "github/copilot-plugins" }
    }
  },

  "telemetryEnabled": true,
  "sessionRetentionDays": 90,
  "preventSleepEnabled": true
}
```

Full example: [`references/settings.example.json`](references/settings.example.json).

### Key-by-key

| Key | Recommended | Why |
|-----|-------------|-----|
| `model` | `claude-opus-4.7` (or `gpt-5.4` for faster turns) | Default model the agent runs on. Microsoft staff: `claude-opus-4.7-xhigh` is available with extra reasoning depth. Override per session with `/model`. |
| `renderMarkdown` | `true` | Pretty-prints tool output that contains markdown. Off only if you want raw bytes. |
| `showReasoning` | `false` | Hides the model's chain-of-thought scratchpad. Toggle to `true` when debugging odd agent behavior. |
| `allowedUrls` | `raw.githubusercontent.com`, `docs.github.com` (+ `localhost:*` while developing) | Pre-approved URLs the agent can fetch without confirmation. Keep tight — every entry is a trust grant. |
| `sessionSync` | `[{"origin": "*", "level": "user"}]` | **High-value.** Roams session history across machines via your GitHub account. `level: "user"` syncs at user scope (not per-repo). |
| `trustedFolders` | absolute paths to your active repos | Suppresses the "trust this folder?" prompt when you cd in. Add only folders you actually own. |
| `extraKnownMarketplaces` | `copilot-plugins` (everyone), `work-iq` (Microsoft only) | Enables `copilot plugin install <name>@<marketplace>` to resolve from these GitHub repos. |
| `telemetryEnabled` | `true` | Helps the team improve the runtime. Set `false` only if your org policy requires it. |
| `sessionRetentionDays` | `90` | How long session-state survives. Drop to 30 if disk is tight. |
| `preventSleepEnabled` | `true` | Keeps the OS awake while a long-running agent task is in flight. Off on laptops on battery. |
| `disabledSkills` | `[]` | Per-skill kill switch. Use to silence a noisy auto-trigger. |

### Microsoft staff: enable the work-iq marketplace

Add to `extraKnownMarketplaces` and install three plugins:

```json
"extraKnownMarketplaces": {
  "copilot-plugins": {
    "source": { "source": "github", "repo": "github/copilot-plugins" }
  },
  "work-iq": {
    "source": { "source": "github", "repo": "microsoft/work-iq" }
  }
}
```

```bash
copilot plugin install workiq@work-iq
copilot plugin install microsoft-365-agents-toolkit@work-iq
copilot plugin install workiq-productivity@work-iq
```

Then in `settings.json`:

```json
"enabledPlugins": {
  "workiq@work-iq": true,
  "microsoft-365-agents-toolkit@work-iq": true,
  "workiq-productivity@work-iq": true
}
```

The work-iq family includes the M365 Agents Toolkit plugin.

---

## Permissions & autoApprove

Copilot CLI tracks two layers of approval state:

1. **`m-settings.json` → `permissions`** (managed, but configurable via
   the UI): `autoApproveReadOnly` (safe to enable) and a per-server
   `autoApprove` map (be selective).
2. **`permissions-config.json`** (per-folder, auto-managed): every time
   you answer **"Yes, always for this folder"** to a tool prompt, the
   approval lands here. Don't edit this file — it's append-only state.

### Safe defaults

| Setting | Safe? | Notes |
|---------|-------|-------|
| `autoApproveReadOnly: true` | ✅ Yes | Read-only operations (file reads, `git log`, `Get-ChildItem`, MCP `*_search` / `*_fetch` / `*_list` tools) skip the prompt. The runtime classifies these conservatively. |
| `servers.filesystem.autoApprove: true` | ✅ Generally yes | Filesystem MCP is already sandboxed to the cwd / trusted folders. |
| `servers.playwright.autoApprove: true` | ✅ Yes if `--isolated` | Ephemeral profile + headless = low blast radius. Disable if you ever drop `--isolated`. |
| `servers.shell.autoApprove: true` | ❌ **NEVER** | Shell tool runs arbitrary commands. Always confirm. |
| `servers.<azure-mcp>.autoApprove: true` | ❌ No | Azure MCP can mutate cloud resources. Always confirm. |
| Per-folder "Yes, always" for `Remove-Item`, `Stop-Process`, `az ... delete` | ❌ Avoid | Even per-folder, blanket-approving destructive commands is how data dies. |

### Inspecting your current state

```powershell
# Windows
Get-Content $env:USERPROFILE\.copilot\m-settings.json |
  python -c "import json,sys; d=json.load(sys.stdin); p=d.get('permissions',{}); print('autoApproveReadOnly:', p.get('autoApproveReadOnly')); print('servers:'); [print(' ', s, v) for s,v in p.get('servers',{}).items()]"
```

```bash
# macOS / Linux
jq '.permissions | {autoApproveReadOnly, servers}' ~/.copilot/m-settings.json
```

---

## Sync strategy

### Session sync (cross-machine session history)

`sessionSync: [{"origin": "*", "level": "user"}]` in `settings.json`
mirrors session state to your GitHub account. On a second machine where
you're logged in as the same user, sessions reappear in `/sessions`.

- `level: "user"` = sync everything you do (recommended for laptops + a
  workstation owned by the same person).
- `level: "repo"` = sync only sessions in repos that explicitly opt in
  via `.copilot/config.json` in the repo root. Tighter blast radius.
- `origin: "*"` = match any GitHub host (use a specific origin if your
  org runs GHEC + GHES side by side).

### User-scope vs project-scope skills

Skills install to one of two locations:

| Scope | Path | When |
|-------|------|------|
| **User** | `~/.copilot/skills/<name>/` | Skills you use across **every** repo (e.g. `gbb-humanizer`, `azure-tenant-isolation`, this skill itself). Install with `--scope user`. |
| **Project** | `<repo>/.copilot/skills/<name>/` | Skills tightly coupled to one project (rare). Travels with the repo via git. |

When you edit a skill in this catalog (`awesome-gbb`) and want the
runtime to pick it up immediately, mirror the change to user scope:

```powershell
# Windows — keep in lock-step with the repo source of truth
robocopy `
  C:\path\to\awesome-gbb\skills\<skill> `
  $env:USERPROFILE\.copilot\skills\<skill> `
  /MIR /XD .git /NFL /NDL /NJH /NJS

# Verify SHA256 parity
Get-FileHash `
  C:\path\to\awesome-gbb\skills\<skill>\SKILL.md, `
  $env:USERPROFILE\.copilot\skills\<skill>\SKILL.md `
  -Algorithm SHA256
```

This is the same pattern documented in `awesome-gbb/AGENTS.md` § 6.
Source-of-truth lives in the repo; user scope is a runtime mirror.

---

## Bootstrap procedure (agent-executable)

When invoked with "set up my fresh machine" or equivalent, follow this
procedure. **Each step is an explicit checkpoint — confirm with the user
before moving to the next.**

### Step 1 — Detect existing state

```powershell
"=== Copilot CLI version ==="; copilot --version
"=== ~/.copilot/ contents ==="
Get-ChildItem $env:USERPROFILE\.copilot -Force | Select-Object Mode,Name | Format-Table -AutoSize
"=== existing mcp-config.json (if any) ==="
$mcp = "$env:USERPROFILE\.copilot\mcp-config.json"
if (Test-Path $mcp) { Get-Content $mcp -Raw } else { "(none)" }
"=== existing settings.json (if any) ==="
$s = "$env:USERPROFILE\.copilot\settings.json"
if (Test-Path $s) { Get-Content $s -Raw } else { "(none)" }
```

If `copilot --version` fails, stop and direct the user to install GHCP
CLI first (`gh extension install github/gh-copilot` then
`gh copilot install` per current install docs — link the user to
<https://docs.github.com/copilot/github-copilot-in-the-cli>).

### Step 2 — Back up current config

```powershell
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$bak = "$env:USERPROFILE\.copilot\backup-$ts"
New-Item -ItemType Directory -Path $bak -Force | Out-Null
foreach ($f in 'settings.json','mcp-config.json') {
  $src = "$env:USERPROFILE\.copilot\$f"
  if (Test-Path $src) { Copy-Item $src $bak\ -Force }
}
"Backed up to: $bak"
```

### Step 3 — Choose MCP server tier

Ask the user: **"no-key trio (mslearn + Azure + Playwright) or full six
(adds context7, tavily, mem0 — needs API keys)?"**

Present `references/mcp-config.example.json` for the trio,
`references/mcp-config.full.json` for the six. Merge into existing
`mcp-config.json` (don't overwrite servers the user already has).

### Step 4 — Apply settings.json baseline

Read `references/settings.example.json`. Merge into existing
`settings.json` keeping the user's existing values where they exist.
**Specifically**:

- `trustedFolders` → ask the user which folders to trust; do NOT carry
  over the example placeholder strings.
- `model` → ask only if the user doesn't already have one set.
- `extraKnownMarketplaces.work-iq` → ask the user "Are you Microsoft
  staff?" before adding.

### Step 5 — Install plugins (Microsoft staff only)

If user confirmed Microsoft staff in Step 4:

```powershell
copilot plugin install workiq@work-iq
copilot plugin install microsoft-365-agents-toolkit@work-iq
copilot plugin install workiq-productivity@work-iq
```

The work-iq family includes the M365 Agents Toolkit plugin — install
via `copilot plugin install microsoft-365-agents-toolkit@work-iq`.

### Step 6 — Verify

```powershell
"=== settings.json after merge ==="; Get-Content $env:USERPROFILE\.copilot\settings.json
"=== mcp-config.json after merge ==="; Get-Content $env:USERPROFILE\.copilot\mcp-config.json
"=== plugins installed ==="; copilot plugin list 2>$null
"=== diff vs backup ==="; Compare-Object `
  (Get-Content "$bak\settings.json" -ErrorAction SilentlyContinue) `
  (Get-Content "$env:USERPROFILE\.copilot\settings.json")
```

Restart any running `copilot` session so the new MCP servers load.
Inside the new session run `/mcp` and confirm all expected servers
appear (status: ✅ connected).

### Step 7 — Recommended skills

Suggest the user install (or sync to user scope) the GBB-recommended
skill set per the README:

```bash
gh skill install aiappsgbb/awesome-gbb threadlight-design --scope user
gh skill install aiappsgbb/awesome-gbb threadlight-deploy --scope user
gh skill install aiappsgbb/awesome-gbb foundry-hosted-agents --scope user
gh skill install aiappsgbb/awesome-gbb foundry-observability --scope user
gh skill install aiappsgbb/awesome-gbb azure-tenant-isolation --scope user
gh skill install aiappsgbb/awesome-gbb gbb-humanizer --scope user
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| MCP server doesn't appear in `/mcp` after editing config | Session was already running | Restart `copilot`. Config loads at session start, not on edit. |
| `Azure` MCP returns "not authenticated" | Copilot CLI inherited a different `AZURE_CONFIG_DIR` than your `az` shell | Set `AZURE_CONFIG_DIR` **before** launching `copilot`. See `azure-tenant-isolation`. |
| `mslearn` returns 0 results | URL drift or transient API issue | Confirm <https://learn.microsoft.com/api/mcp> still resolves. Retry in 30s. |
| `Playwright` launch crashes on Windows | `npx` not on PATH for the spawned process | Use the `cmd /c` wrapper as shown above. |
| `mem0` returns "module not found" | Python module not installed | `pip install mem0-mcp-server` in the same Python env Copilot CLI invokes. |
| Tools that should be auto-approved still prompt | `autoApproveReadOnly` only covers *classified-as-read-only* tools | Use the per-server `autoApprove: true` map (carefully — only for read-only servers). |
| `permissions-config.json` is huge | Years of "Yes, always" answers accumulated | Safe to delete — Copilot CLI re-prompts and rebuilds it. |
| Session sync not roaming | `level: "repo"` set on origin, or wrong GitHub user | Check `settings.json → sessionSync`; `gh auth status` to confirm the same user is logged in on both machines. |
| Plugin install fails: `marketplace not found` | Marketplace not registered in `extraKnownMarketplaces` | Add the entry per the snippet above, then retry. |
| Edits to `m-settings.json` keep reverting | That file is **managed** — the runtime rewrites it | Move your edit to `settings.json`. The two are merged at runtime. |

---

## See Also

| Skill | Use When |
|-------|----------|
| [**skill-creator**](../skill-creator/) | You want to **author** a new skill (this skill **configures** the runtime that loads skills — different concern). |
| [**azure-tenant-isolation**](../azure-tenant-isolation/) | You work across multiple Azure tenants. The `Azure` MCP server above honors the per-shell `AZURE_CONFIG_DIR` set by that skill. |
| [**ip-catalog**](../ip-catalog/) | You want to discover GBB IP via MCP — installs as another MCP server (`gbb_ip_catalog`) on top of this baseline. |
| [**gbb-humanizer**](../gbb-humanizer/) | After this skill helps generate prose (e.g. a personal `~/.copilot/AGENTS.md`), polish it. |

---

## References

- [`references/mcp-config.example.json`](references/mcp-config.example.json) — minimal no-key trio
- [`references/mcp-config.full.json`](references/mcp-config.full.json) — full six with placeholder keys
- [`references/settings.example.json`](references/settings.example.json) — baseline `settings.json`
- GitHub Copilot CLI docs: <https://docs.github.com/copilot/github-copilot-in-the-cli>
- Microsoft Learn MCP API: <https://learn.microsoft.com/api/mcp>
- Azure MCP server: <https://github.com/Azure/azure-mcp>
- Playwright MCP: <https://github.com/microsoft/playwright-mcp>
- Context7: <https://context7.com/>
- Tavily: <https://tavily.com/>
- mem0: <https://mem0.ai/>

---

## GBB changelog

| Version | Notes |
|---------|-------|
| 1.0.0 | Initial seed. Distilled from a live GBB engineer's `~/.copilot/`. Six recommended MCP servers (mslearn, Azure, Playwright, context7, tavily, mem0). `settings.json` baseline with `model`, `sessionSync`, `allowedUrls`, `trustedFolders`, `extraKnownMarketplaces`. Microsoft staff plugins (work-iq family). `autoApprove` safe-default matrix. Step-by-step bootstrap procedure (detect → backup → tier → settings → plugins → verify). |

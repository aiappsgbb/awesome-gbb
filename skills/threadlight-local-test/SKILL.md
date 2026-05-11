---
name: threadlight-local-test
description: >
  Run a Threadlight design output (FoundryChatClient agent + FastMCP
  server + workspace UI + sample data) locally without `azd up` — for
  fast iteration loops in GitHub Copilot CLI / Cowork / Clawpilot.
  Three patterns: (1) MCP-direct — register the PoC's local MCP at
  `~/.copilot/mcp.json` so the CLI calls tools natively; (2)
  Smoke-client — invoke `agent.run_async()` directly bypassing the
  ResponsesHostServer; (3) Local-stack — docker-compose with Cosmos
  emulator + nginx for end-to-end smoke. Replaces azure-deployed
  Cosmos / Search / hosted-agent runtime with local stand-ins; AOAI
  calls still go to a real deployment.
  USE FOR: local test, smoke test, run agent locally, dev loop, no
  azd, copilot cli mcp, ghcp local agent, faster iteration, debug
  tools without redeploying, prompt tuning, cowork iteration.
  DO NOT USE FOR: prod deployment (use threadlight-deploy), final
  pre-pilot validation (use threadlight-safe-check), Foundry
  hosted-agent runtime testing in cloud (use foundry-evals).
---

# Threadlight — Local Test Loop (no azd up)

Run a generated PoC entirely on your dev box so you can iterate on
**tools**, **prompts**, and **workspace UI** in seconds — not in the
20-30 min round-trip of `azd deploy`. Designed for use **inside**
GitHub Copilot CLI, Cowork, or Clawpilot, where you want to hand
the running agent / MCP server to the CLI itself for hands-on
testing.

> **What this skill is NOT.** This is not a "make Foundry run on
> your laptop" skill — Foundry hosted-agent runtime stays in Azure.
> What this skill *is* is the recipe for running the **same agent
> code, the same MCP server code, the same workspace HTML** on
> localhost so you can debug fast, then redeploy via
> `threadlight-deploy` when you're happy.

---

## When to use which pattern

| Pattern | What it runs | When to use |
|---------|--------------|-------------|
| **1. MCP-direct** (CLI ↔ MCP) | Just the PoC's FastMCP server on `localhost:8000`; CLI calls tools natively | You're iterating on **MCP tool implementation** (DB queries, business rules, error handling). The CLI itself is the agent. |
| **2. Smoke-client** (CLI → Python → Agent) | The PoC's `Agent + FoundryChatClient` invoked via `agent.run_async()` from a smoke script | You're iterating on the **prompt** or the **agent's tool-orchestration** behaviour. Skips the `ResponsesHostServer` HTTP layer. |
| **3. Local-stack** (compose) | All of: MCP server + Cosmos emulator + workspace UI on nginx + (optional) Search mock | You're testing the **end-to-end flow** (UI → bot → agent → MCP → DB) before redeploying. Closest to prod fidelity short of real Azure. |

You'll typically run **#1** for tool dev, **#2** for prompt tuning,
and **#3** as a final pre-deploy gate.

---

## Prerequisites (one-time, dev box)

| Need | Why | Install |
|------|-----|---------|
| **Python 3.13** + `uv` | Run agent/MCP code | [uv install](https://docs.astral.sh/uv/) |
| **Docker Desktop** (or Rancher) | Cosmos emulator + nginx | Standard install |
| **Azure OpenAI deployment** of `gpt-5.4-mini` (or any model) | Agent needs a real LLM | Any AOAI account; the cheapest path is a personal sandbox sub. **The skill does NOT require Foundry locally.** |
| **`az` logged in** to the AOAI tenant | DefaultAzureCredential in the agent code resolves to your `az` token | `az login --tenant <tid>` (per `azure-tenant-isolation`) |
| **GitHub Copilot CLI** ≥ 1.0.40 | For Pattern 1 (MCP-direct) | `gh extension install github/gh-copilot-cli` |

> **Bring-Your-Own-Foundry option.** If you have a Foundry project,
> Patterns 2 and 3 can use `FoundryChatClient(project_endpoint=...)`
> exactly as in production. If you don't, swap to plain `OpenAIClient`
> pointed at AOAI directly — the agent code is identical aside from
> the client constructor. See `references/local-stack/local_smoke.py`
> for both forms.

---

## Pattern 1 — MCP-direct (Copilot CLI ↔ local MCP)

The cleanest dev loop for **tool development**. The CLI itself acts
as the agent; you call tools natively from natural language.

### Setup (3 lines)

```powershell
# 1. Run the PoC's MCP server locally
cd <poc-root>/src/mcp_server
uv run python main.py     # binds to http://localhost:8000/mcp

# 2. Register it with Copilot CLI (per-user; persists)
copilot mcp add <poc-name>-local --url http://localhost:8000/mcp

# 3. Restart the CLI session
copilot
```

### Iteration loop

In the CLI, ask: `"call list_open_disputes; what do you see?"`
→ the CLI invokes the local tool directly, you see the JSON
response, you tweak `mcp_server/main.py`, the dev-loop reload picks
it up (FastMCP supports `--reload`), you re-ask the CLI.

**Why this is fast:** zero LLM round-trips for the dev parts you
don't care about (no agent prompt to debug here); the CLI's
built-in agent calls your tool once, you read the JSON, you fix.

> **Pitfall.** If your MCP server reads from Azure resources
> (Cosmos, Search) using `DefaultAzureCredential`, the local
> process needs to authenticate to those — either use the dev
> stack from Pattern 3 (local Cosmos), or `az login` against the
> tenant that owns the real cloud resources. See
> `references/cli-integration/copilot_mcp_register.md` for the
> full setup including a localhost MCP that reads from cloud
> Cosmos via your `az` token.

See `references/cli-integration/copilot_mcp_register.md`.

---

## Pattern 2 — Smoke-client (direct `agent.run_async()`)

For **prompt tuning** and **agent-orchestration** debugging, skip
the `ResponsesHostServer` HTTP layer entirely. Build the agent
in-process and call `run_async()` directly.

### Worked example

`tests/local_smoke.py` (template ships in
`references/local-stack/local_smoke.py`):

```python
import asyncio
import os
from agent.container import build_agent     # PoC's existing factory

async def main():
    os.environ.setdefault("MCP_SERVER_FQDN", "localhost:8000")
    os.environ.setdefault("MODEL_DEPLOYMENT_NAME", "gpt-5.4-mini")
    os.environ.setdefault("FOUNDRY_PROJECT_ENDPOINT",
                          "https://<your-foundry>.services.ai.azure.com/api/projects/<proj>")

    agent = build_agent()
    while True:
        prompt = input("\n> ").strip()
        if not prompt or prompt in {"quit", "exit"}: break
        async for event in agent.run_streaming(prompt):
            print(event.text, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
```

Then: `uv run python tests/local_smoke.py` — interactive REPL
against the local agent. Fast iteration on prompt + tool selection
without the full ACA round-trip.

### Variant — drive from the CLI

For natural-language prompts dispatched **by** Copilot CLI
(useful when you want the CLI to script a multi-turn smoke
session), wrap as a one-shot:

```python
# tests/local_smoke_oneshot.py
import asyncio, sys
from agent.container import build_agent
async def go(prompt):
    agent = build_agent()
    out = await agent.run_async(prompt)
    print(out.messages[-1].text)
asyncio.run(go(" ".join(sys.argv[1:])))
```

CLI: `uv run python tests/local_smoke_oneshot.py "investigate case dc001"`

---

## Pattern 3 — Local stack (docker-compose)

For **end-to-end smoke** with real Cosmos, real workspace UI, and
the same FastMCP server you'd deploy. Closest fidelity to prod
without the deploy cost.

### Stack components

```
┌────────────────────────────┐  ┌──────────────────────────┐  ┌─────────────────────────────┐
│  Workspace UI              │  │  MCP Server (FastMCP)    │  │  Cosmos DB Emulator         │
│  http://localhost:8080     │──▶  http://localhost:8000   │──▶  https://localhost:8081     │
│  (nginx serving static/)   │  │  (Python uv run)         │  │  (mcr.microsoft.com/cosmosdb)│
└────────────────────────────┘  └──────────────────────────┘  └─────────────────────────────┘
                                          │
                                          ▼
                              ┌──────────────────────────┐
                              │  Smoke client (Pattern 2) │
                              │  posts to MCP + agent     │
                              └──────────────────────────┘
```

### Bring up

```powershell
cd <poc-root>
cp references/local-stack/.env.local.example .env.local
# Edit .env.local: set FOUNDRY_PROJECT_ENDPOINT, MODEL_DEPLOYMENT_NAME

docker compose -f references/local-stack/compose.local.yaml --env-file .env.local up -d

# Seed Cosmos with sample data (the PoC's own factory script)
uv run python tests/seed_local_cosmos.py    # template provided

# Smoke
uv run python tests/local_smoke.py
```

### Tear down

```powershell
docker compose -f references/local-stack/compose.local.yaml down -v
```

See `references/local-stack/compose.local.yaml` for the full
file (Cosmos + nginx; MCP server intentionally runs OUTSIDE
docker so you can iterate on Python without rebuilding).

> **AI Search note.** No good local emulator exists. For
> RAG-heavy PoCs, either: (a) point at a real cheap dev Search
> instance via env var; (b) use `references/local-stack/mock_search.py`
> as a drop-in shim that returns canned hits from a local JSON
> file. Option (b) is fine for prompt iteration but doesn't
> exercise hybrid/vector ranking realistically.

---

## What this skill ships

```
references/
├── local-stack/
│   ├── compose.local.yaml        # Cosmos emulator + nginx
│   ├── .env.local.example        # template env file
│   ├── local_smoke.py            # interactive REPL (Pattern 2)
│   ├── local_smoke_oneshot.py    # one-shot for CLI scripting
│   ├── seed_local_cosmos.py      # Cosmos emulator seeding
│   ├── mock_search.py            # in-memory AI Search shim
│   └── cosmos_emulator_notes.md  # gotchas (SSL, perf, ports)
└── cli-integration/
    ├── copilot_mcp_register.md   # Pattern 1 setup walkthrough
    └── ghcp_cowork_recipe.md     # Cowork / GHCP-CLI dev loop
```

Each file is **drop-in** — copy into the PoC's `tests/` (Python
files), `infra/` (compose), or root (`.env.local`). The skill
templates use `<poc-name>` and `<table-name>` placeholders that
the developer string-replaces.

---

## Anti-patterns

- ❌ **Run the agent against prod Cosmos / Search by accident.**
  Always `az account show` before starting; the smoke client uses
  `DefaultAzureCredential` and will happily auth into any
  subscription you're logged into. Per `azure-tenant-isolation`,
  set `AZURE_CONFIG_DIR` to a dev-tenant alias before any
  smoke run.
- ❌ **Use `ollama` / local LLM instead of AOAI.** Tempting for
  offline dev, but the production agent is tuned for `gpt-5.4`
  family behaviour. Tool-calling reliability differs significantly
  on smaller open models, so smoke results don't transfer. See
  `foundry-hosted-agents` § "Model selection — gpt-5.4 vs mini".
- ❌ **Skip Pattern 1 because "the CLI is just a chat box".**
  Copilot CLI's MCP integration is genuinely the fastest tool-dev
  loop available — write a tool, save the file, ask the CLI to
  call it, read the result, fix. No agent prompt to disentangle.
- ❌ **Run Cosmos emulator on macOS / Linux ARM and expect SSL to
  Just Work.** The Linux emulator image is x86-only and has known
  SSL quirks; the smoke client must trust the emulator cert or
  set `COSMOS_VERIFY_SSL=false` on `CosmosClient`. See
  `cosmos_emulator_notes.md`.
- ❌ **Treat Pattern 3 as a substitute for `threadlight-safe-check`.**
  The local stack does NOT verify Bicep, RBAC assignments, ACA
  diagnostic settings, or any of the cloud-shaped concerns. It's
  a fast smoke, not a deploy gate. Run safe-check after `azd up`.
- ❌ **Commit `.env.local` to the PoC repo.** It typically contains
  the AOAI key or Foundry endpoint. Add `.env.local` to
  `.gitignore` in every PoC scaffold.

---

## Cost note

| Pattern | Cloud spend | Why |
|---------|-------------|-----|
| 1 (MCP-direct) | $0 if MCP reads only local data; tiny if MCP reads cloud Cosmos / Search | CLI's own LLM is GitHub-billed |
| 2 (smoke-client) | AOAI tokens only | Agent calls real `gpt-5.4-mini`; ~$0.001 per smoke turn |
| 3 (local-stack) | AOAI tokens + (optional) cloud Search | Same as 2; Cosmos local; UI local |

A typical day of dev iteration burns < $1 of AOAI tokens. Cosmos
emulator is free.

---

## Composition with other skills

- **Comes before `threadlight-deploy`.** Local-test → safe → push
  to `azd up`. Failing here = don't deploy.
- **Comes after `threadlight-design`.** The design output's
  `agent/container.py` factory is the entry point Pattern 2 calls.
  If your `build_agent()` factory bakes in cloud-only assumptions
  (e.g. hardcoded Foundry endpoint), refactor it to read from
  env-vars first; that's the prerequisite for local test.
- **Pairs with `foundry-hosted-agents`.** The Pattern 2 smoke uses
  the same `Agent + FoundryChatClient` you ship to ACA; the only
  difference is no `ResponsesHostServer` wrapping it. If
  `foundry-hosted-agents` says the agent needs `MCPStreamableHTTPTool
  + parse_tool_results=_mcp_text_extractor`, that's still required
  here.
- **Pairs with `azd-patterns`.** When the local smoke fails at
  step "agent calls MCP tool and gets `[<Content object>]`",
  that's `gap-009` from `foundry-hosted-agents` — the local stack
  is identical to prod here so the same fix applies.
- **Cross-cuts `azure-tenant-isolation`.** Your local AOAI / Foundry
  must be in the dev tenant; never the prod one. The smoke
  client auths via `DefaultAzureCredential` so the active
  `AZURE_CONFIG_DIR` decides which tenant gets billed.

---

## Reference files

| File | Purpose |
|------|---------|
| `references/local-stack/compose.local.yaml` | Docker compose: Cosmos emulator + nginx for UI |
| `references/local-stack/.env.local.example` | Template env file (Foundry endpoint, AOAI deployment name, etc.) |
| `references/local-stack/local_smoke.py` | Interactive REPL — Pattern 2 entry point |
| `references/local-stack/local_smoke_oneshot.py` | One-shot CLI driver (for scripting from Copilot CLI) |
| `references/local-stack/seed_local_cosmos.py` | Bulk-load sample data into the emulator |
| `references/local-stack/mock_search.py` | In-memory AI Search shim for offline RAG smoke |
| `references/local-stack/cosmos_emulator_notes.md` | Cosmos emulator gotchas (SSL, ARM, ports) |
| `references/cli-integration/copilot_mcp_register.md` | Pattern 1 — full Copilot CLI MCP registration walkthrough |
| `references/cli-integration/ghcp_cowork_recipe.md` | GHCP CLI / Cowork-specific dev loop notes |

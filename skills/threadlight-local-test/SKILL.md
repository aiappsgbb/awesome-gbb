---
name: threadlight-local-test
description: >
  Run a threadlight-designed PoC locally without `azd up`. Four patterns:
  (0) **Quickstart (default)** — `python -m threadlight_quickstart` boots
  a MAF Agent + SkillsProvider + JSON stub tools + Streamlit UI on
  localhost:8501; no Docker, no MCP boot, one LLM dep (Foundry project
  OR Azure OpenAI). Closes design → screen-shareable demo to <30 min.
  (1) MCP-direct — register the PoC's local MCP at `~/.copilot/mcp.json`;
  (2) Smoke-client — `agent.run_async()` bypassing ResponsesHostServer;
  (3) Local-stack — docker-compose + Cosmos emulator (Linux/Windows x86
  only — fragile on macOS ARM). LLM calls always hit a real deployment.
  USE FOR: local test, smoke test, run agent locally, dev loop, no azd,
  copilot cli mcp, faster iteration, prompt tuning, cowork iteration,
  demo rehearsal, screen-shareable PoC, streamlit demo, MAF
  SkillsProvider quickstart.
  DO NOT USE FOR: prod deployment (use threadlight-deploy), pre-pilot
  validation (use threadlight-safe-check), hosted-agent runtime testing
  in cloud (use foundry-evals).
metadata:
  version: "1.1.0"
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
| **0. Quickstart** (default) | `python -m threadlight_quickstart` → MAF `Agent + SkillsProvider` + JSON stub tools + Streamlit UI on `localhost:8501` | **First reach-for after `threadlight-design`.** Closes the design → screen-shareable demo loop to <30 min. Zero Docker, zero MCP server boot, one LLM dep (Foundry project OR AOAI deployment). |
| **1. MCP-direct** (CLI ↔ MCP) | Just the PoC's FastMCP server on `localhost:8000`; CLI calls tools natively | You're iterating on **MCP tool implementation** (DB queries, business rules, error handling). The CLI itself is the agent. |
| **2. Smoke-client** (CLI → Python → Agent) | The PoC's `Agent + FoundryChatClient` invoked via `agent.run_async()` from a smoke script | You're iterating on the **prompt** or the **agent's tool-orchestration** behaviour. Skips the `ResponsesHostServer` HTTP layer. |
| **3. Local-stack** (compose) ⚠️ | All of: MCP server + Cosmos emulator + workspace UI on nginx + (optional) Search mock | End-to-end smoke before redeploying. **Linux / Windows x86 only** — Cosmos emulator container is fragile on macOS ARM; use Pattern 0 there. |

Reach for **Pattern 0** first. Drop to **Pattern 1** when you need
to iterate on the real MCP server. Use **Pattern 2** for headless
prompt tuning that needs to be driven from the CLI. **Pattern 3** is
a pre-deploy parity check on platforms where the Cosmos emulator
container actually works.

---

## Pattern 0 — Quickstart (default)

The new default for "I just finished `threadlight-design`, now I want
to see it run." Consumes what design already emits — `specs/sample-data/`,
`src/agent/skills/<name>/SKILL.md` — and gives you a MAF agent + a
chat UI on `localhost:8501` without ever touching Docker, the MCP
server, or a real Cosmos.

### What you need

| Need | Why | One-time? |
|------|-----|-----------|
| **Python ≥ 3.10** + `pip` (or `uv`) | Run the reference package | Yes |
| **A threadlight-designed PoC** (the cwd at minimum has `specs/sample-data/*.json`) | Pattern 0 auto-discovers it | Per PoC |
| **One LLM endpoint** — Foundry project URL **OR** Azure OpenAI deployment | The only Azure dep | Per tenant (shared GBB sandbox is fine) |
| **`az login`** to the LLM tenant | `DefaultAzureCredential` picks it up | Per tenant |

> **No Docker. No Cosmos emulator. No MCP server boot.** Pattern 0
> replaces all three with an in-memory dict-of-records loaded from
> `specs/sample-data/<entity>.json` and three CRUD tools per entity
> (`list_<entity>`, `get_<entity>`, `update_<entity>`).

### The bootstrap (one-time per PoC)

```bash
# 1) Install the quickstart package once (editable, from the catalog)
pip install -e <awesome-gbb>/skills/threadlight-local-test/references/quickstart

# 2) Drop the env template into the PoC and edit it
cp <awesome-gbb>/skills/threadlight-local-test/references/quickstart/.env.local.example .env.local
$EDITOR .env.local        # set FOUNDRY_PROJECT_ENDPOINT + MODEL_DEPLOYMENT_NAME (or LLM_BACKEND=aoai + AOAI vars)
echo .env.local >> .gitignore

# 3) Sanity-check the wiring without a live LLM round-trip (<5s)
python -m threadlight_quickstart --check
```

### The loop (every time)

```bash
az login --tenant <dev-tid>          # per azure-tenant-isolation skill
python -m threadlight_quickstart     # Streamlit on http://localhost:8501
```

Or with the demo-prompt pump pre-loaded so you can step through the
prep-guide acts hands-free:

```bash
python -m threadlight_quickstart --simulator
```

`--simulator` reads prompts in priority order from:

1. `<poc-root>/tests/demo-prompts.txt` (one prompt per line; `#` comments allowed)
2. `<poc-root>/specs/prep-guide.html` § *Demo Script* (regex on `<strong>Type this:</strong>` blocks)

### How the tools come from your SPEC

For every `specs/sample-data/<entity>.json` discovered, Pattern 0
registers three MAF `@tool`-decorated callables backed by an
in-memory `InMemoryStore`:

| Tool | Returns | Notes |
|------|---------|-------|
| `list_<entity>(**filters)` | `list[dict]` | Equality match on each filter kwarg; no filter → all records |
| `get_<entity>(id)` | `dict \| None` | Lookup by record id |
| `update_<entity>(id, **fields)` | `dict` | Mutates the in-memory snapshot; **reset every launch** |

The agent's `SkillsProvider` loads every `src/agent/skills/<name>/SKILL.md`
under `from_paths(skills_dir)` — same progressive-disclosure shape
documented in [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md)
§ *Skill Loading*, so the prompt the agent sees is identical to prod.

### Custom tools (when CRUD isn't enough)

For cross-entity joins, derived fields, business rules — drop a
`tests/quickstart_tools.py` next to the PoC, exposing:

```python
def register(tools: list, stores: dict) -> list:
    """Return extra MAF tools to append to the auto-generated CRUD set."""
    from agent_framework import tool

    @tool
    def reassign_urgent(assignee: str) -> int:
        urgent = stores["tickets"].list_all(severity="urgent")
        for row in urgent:
            stores["tickets"].update(row["id"], assignee=assignee)
        return len(urgent)

    return [reassign_urgent]
```

`agent_wiring` auto-discovers and calls `register(tools, stores)` after
the CRUD triple is built.

### What ships in the reference package

```
references/quickstart/
├── pyproject.toml                 # pip-installable; pins streamlit + agent-framework
├── threadlight_quickstart/
│   ├── __main__.py                # `python -m threadlight_quickstart`
│   ├── cli.py                     # argparse: --check, --info, --simulator, --port
│   ├── discover.py                # walks up cwd for the canonical PoC layout
│   ├── agent_wiring.py            # Agent + SkillsProvider + tool registration
│   ├── stub_tools.py              # InMemoryStore + CRUD tool factory
│   ├── simulator.py               # demo-prompt cursor
│   └── ui_streamlit.py            # the Streamlit chat page
├── .env.local.example             # env-var template
├── Makefile.demo                  # drop-in for PoCs that want `make demo`
├── fixture-poc/                   # 1-skill, 1-entity toy PoC (smoke target)
└── tests/                         # pytest against fixture-poc
```

### When Pattern 0 is **not** the right answer

- **You need the real React workspace UI render** → Pattern 1 + run
  the PoC's own `npm run dev:workspace` separately. Pattern 0 ships
  Streamlit only on purpose (zero Node toolchain).
- **You're debugging the real MCP server** → Pattern 1. Pattern 0
  bypasses the MCP layer entirely.
- **You need real Cosmos / Search semantics** (ranking, partition keys,
  RU shape) → Pattern 3 on Linux/Windows x86, or `azd up` to a dev sub.
- **You need multi-agent orchestration** → Pattern 2.

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

> ⚠️ **Linux / Windows x86 only.** The Cosmos DB emulator container
> (`mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator`) does not
> run reliably on **macOS Apple Silicon (arm64)** — there is no native
> ARM image as of 2026-05, and the x86 image under Rosetta fails the
> internal endpoint validation (SSL bind on `0.0.0.0:8081`).
> **On macOS ARM, use Pattern 0** for the design → demo loop and
> Pattern 1/2 for tool / prompt work; reach for Pattern 3 only on a
> Linux box or Windows x86 dev machine when you need true Cosmos-shape
> parity before `azd up`.

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

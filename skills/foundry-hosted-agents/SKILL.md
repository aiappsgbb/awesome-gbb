---
name: foundry-hosted-agents
description: >
  Deploy, evaluate, and manage Foundry agents end-to-end: Docker build, ACR push,
  hosted/prompt agent create, container start, batch eval, prompt optimization,
  agent.yaml, dataset curation from traces. Covers the refreshed hosted agents
  preview (April 2026): Agent + FoundryChatClient + ResponsesHostServer pattern,
  azd ai agent extension, identity model, RBAC, and troubleshooting.
metadata:
  version: "1.4.1"
---

# Microsoft Foundry Hosted Agents — Reference Guide

Production-tested patterns for deploying hosted agents on Microsoft Foundry
(refreshed preview, April 2026). Covers the `Agent` + `FoundryChatClient` +
`ResponsesHostServer` (MAF) variant exclusively.

> **⚠️ MAF 1.4.0 cutover (May 2026) — three breaking changes.** If you have
> hosted agents pinned to `agent-framework-core` 1.3.x or earlier, they
> will start returning `401 Unauthorized` / `server_error` on every
> Responses request once Azure completes the rolling Foundry data-plane
> rename. **You must rebuild the orchestrator image** and re-import the
> agent versions. See [§ MAF 1.4.0 breaking changes](#maf-140-breaking-changes-may-2026)
> for the full migration: `ai.azure.com` token scope, "Foundry User" role
> rename (GUID unchanged), `AzureOpenAIChatClient` removal,
> `:latest` vs `sha256@…` image-tag strategy.

## When to Use

- Deploying a custom container agent to Foundry
- Debugging hosted agent failures (401, 500, import errors)
- Setting up RBAC for agent identities
- Configuring `agent.yaml`, `azure.yaml`, Bicep parameters
- Understanding the refreshed preview changes (packages, identity, invocation)
- **Migrating from MAF 1.3.x → 1.4.0** ([§ below](#maf-140-breaking-changes-may-2026))

---

## MAF 1.4.0 breaking changes (May 2026)

Azure renamed the Foundry data-plane role from **"Azure AI User"** to
**"Foundry User"** and changed the AAD token audience the SDK requests
from `https://cognitiveservices.azure.com/.default` to
`https://ai.azure.com/.default`. **`agent-framework-core` 1.4.0**
(2026-05-14, alongside `agent-framework-foundry-hosting` 1.0.0a260514)
is the first SDK that requests the new scope; everything pinned to 1.3.x
or earlier requests the old scope and gets **`401 Unauthorized`** from
the post-rename data plane.

### The three changes you have to absorb

| # | Change | Symptom on pinned 1.3.x | Fix |
|---|--------|------------------------|-----|
| 1 | **AAD token scope:** `cognitiveservices.azure.com` → `ai.azure.com` | Every Responses request → `401 Unauthorized` (with valid `Foundry User` RBAC) | Upgrade to `agent-framework-core~=1.4.0` + `agent-framework-foundry~=1.4.0` + `agent-framework-foundry-hosting==1.0.0a260514` |
| 2 | **Role display name** "Azure AI User" → "Foundry User" | `az role assignment create --role "Azure AI User"` fails with `RoleDefinitionNotFound` | Use `--role "Foundry User"` OR pin by GUID `53ca6127-db72-4b80-b1b0-d745d6d5456d` (unchanged across the rename — the safest call-site form is the GUID) |
| 3 | **`AzureOpenAIChatClient` removed** from `agent_framework.azure` | `ImportError: cannot import name 'AzureOpenAIChatClient'` after `pip install -U` | Use `OpenAIChatClient(azure_endpoint=..., model=..., credential=...)` from `agent_framework.openai` — see snippet below |

### `AzureOpenAIChatClient` → `OpenAIChatClient` migration

`FoundryChatClient` is the right choice for hosted Foundry agents and is
unaffected. The removal hits **adjacent code paths** that talked directly
to Azure OpenAI (eval judges, batch scoring, sidecar services, agents
that route through APIM):

```python
# OLD (MAF 1.3.x — REMOVED in 1.4.0)
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import get_bearer_token_provider, DefaultAzureCredential
client = AzureOpenAIChatClient(
    endpoint=AZURE_OPENAI_ENDPOINT,
    deployment_name=DEPLOYMENT,
    ad_token_provider=get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    ),
)

# NEW (MAF 1.4.0)
from agent_framework.openai import OpenAIChatClient
from azure.identity import DefaultAzureCredential
client = OpenAIChatClient(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,    # NB: kwarg renamed from `endpoint`
    model=DEPLOYMENT,                         # NB: kwarg renamed from `deployment_name`
    credential=DefaultAzureCredential(),     # SDK derives the right token scope internally
)
```

Drop the explicit `get_bearer_token_provider` / `ad_token_provider` —
`OpenAIChatClient` now derives the scope itself. The unused
`get_bearer_token_provider` import can be removed.

### Image-tag staleness trap (mandatory read for any pilot that pins by digest)

Hosted agent versions reference the orchestrator container by ACR
image **reference**. There are two common shapes:

- `<acr>.azurecr.io/tl-maf-orchestrator:latest` — re-resolves to the
  newest pushed image on every container start. Auto-picks up MAF
  rebuilds the next time the agent provisions.
- `<acr>.azurecr.io/tl-maf-orchestrator@sha256:abc…` — pinned to a
  specific layer digest. Reproducible, but **frozen at the MAF version
  that was in the image when the digest was computed**.

After a MAF 1.4.0 rebuild, agents using `:latest` work; agents using
`@sha256:…` digests from the 1.3.x era keep hitting the old token scope
and fail. **Re-import every hosted agent version** (or pin by digest to
the freshly-built 1.4.0 image) as part of the upgrade. `azd ai agent
deploy` does this automatically if the YAML references `:latest`.

### Rebuild recipe (copy-paste)

```bash
# 1. Upgrade orchestrator pyproject.toml + regenerate uv.lock
sed -i.bak 's/"agent-framework-core[^"]*"/"agent-framework-core~=1.4.0"/' src/orchestrator/pyproject.toml
sed -i.bak 's/"agent-framework-foundry[^"]*"/"agent-framework-foundry~=1.4.0"/' src/orchestrator/pyproject.toml
sed -i.bak 's/"agent-framework-foundry-hosting[^"]*"/"agent-framework-foundry-hosting==1.0.0a260514"/' src/orchestrator/pyproject.toml
(cd src/orchestrator && uv lock)

# 2. ACR remote build — tag with :latest AND a date-pinned tag for forensics
ACR=tl<your-acr-suffix>
az acr build --registry "$ACR" \
  --image "tl-maf-orchestrator:maf14-$(date +%Y%m%d%H%M)" \
  --image "tl-maf-orchestrator:latest" \
  --file src/orchestrator/dockerfile src/orchestrator/

# 3. Re-deploy + re-import each agent so it picks up the fresh image
azd deploy agents
(cd infra/scripts && uv run deploy_job.py)
# Then: azd ai agent show — confirm new image digest under each version
```

> **Why date-pinned tags matter.** `:latest` is fine for the agent
> reference but leaves zero forensic trail in ACR's image history.
> The `maf14-YYYYMMDDHHMM` tag lets you correlate "which agent
> version is running which MAF build?" months later when a regression
> bisect needs it.

---

## Runtime Pattern (MAF Variant)

> **Model selection (verified across recent pilots).** Default
> to **`gpt-5.4`** for production agents that run instruction chains
> with 10+ tool steps (case investigation, multi-source RAG synthesis,
> regulatory drafting). Use **`gpt-5.4-mini`** only for trivial
> 1-2-step flows (single-tool lookups, formatters). The mini variant's
> tool-call discipline degrades sharply on long chains: in recent
> strict-smoke reproducibility on a 7-skill flow went from **1/3** with
> gpt-5.4-mini to **3/3** with gpt-5.4 (same MCP server, same prompts).
> The mini variant tends to call commit-style tools before evidence is
> gathered — partially mitigated by the validate-or-reject pattern in
> `foundry-mcp-aca`, but gpt-5.4 still fixes the root cause.
>
> **Cost/latency note.** `gpt-5.4` GlobalStandard at 50 capacity costs
> a few cents per scenario at idle the deployment ticks negligibly,
> so the typical pilot cost is dominated by the scenarios you actually
> run. Don't downgrade to mini just to save on the deployment standby.

```python
import os
from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from pydantic import Field
from typing import Annotated

client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["MODEL_DEPLOYMENT_NAME"],
    credential=DefaultAzureCredential(),
)

@tool(approval_mode="never_require")
def my_tool(query: Annotated[str, Field(description="Input")]) -> str:
    """Tool description."""
    return "result"

agent = Agent(
    client=client,
    instructions="You are a helpful assistant.",
    tools=[my_tool],
    default_options={"store": False},  # Platform manages history
)

server = ResponsesHostServer(agent)
server.run()  # Serves on port 8088
```

**Key points:**
- `FOUNDRY_PROJECT_ENDPOINT` is **injected by the platform** — never declare in agent.yaml
- `default_options={"store": False}` — hosting platform manages conversation history
- `ResponsesHostServer` handles liveness/readiness probes natively
- `DefaultAzureCredential` resolves to the container's App Service managed identity
- Custom tools use `@tool(approval_mode="never_require")` with `Annotated` type hints

### Skill Loading — `SkillsProvider` (recommended) vs. inline `_load_skills()` (legacy)

> **Authoritative source.** [Microsoft Agent Framework — Agent Skills (Python)](https://learn.microsoft.com/en-us/agent-framework/agents/skills?pivots=programming-language-python).
> `SkillsProvider` is a first-class **MAF Python class** shipped in the same
> `agent_framework` package as `Agent`, `MCPStreamableHTTPTool`, and `@tool`
> (no extra install). It implements the [agentskills.io](https://agentskills.io/)
> 4-stage progressive disclosure pattern:
> **Advertise (~100 tokens/skill) → `load_skill` → `read_skill_resource` → `run_skill_script`**.
> Wired via `context_providers=[skills_provider]` on the `Agent(...)`
> constructor — orthogonal to `tools=[...]`.

> **Cross-link.** The exact same `SkillsProvider.from_paths(skills_dir)`
> wiring shape is what [`threadlight-local-test` **Pattern 0 — Quickstart**](../threadlight-local-test/SKILL.md)
> runs locally against a designed PoC — so the prompt context the local
> demo agent sees is identical to what ships to Foundry.

#### ⚠️ Separation of concerns (read this first)

When `SkillsProvider` is wired, `_load_instructions()` MUST contain **only**
the baseline orchestration prompt (`copilot-instructions.md`) plus
SPEC-derived constants (`config.json`: thresholds, enums, templates).

It MUST NOT also concat `SKILL.md` content. `SkillsProvider` advertises
each skill in ~100 tokens, then the agent calls `load_skill(name)` on
demand. Concatenating both **double-counts** every skill body, blows
out the static prompt, and silently defeats progressive disclosure.

#### Recommended — `SkillsProvider` context provider

Defensive-init helper. The agent stays runnable with `context_providers=[]`
even if the skills directory is missing or a `SKILL.md` is malformed —
critical for ops, since a single broken skill file should not crash the
container at startup.

```python
import os
from pathlib import Path
from agent_framework import Agent, MCPStreamableHTTPTool, SkillsProvider, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential

def _build_skills_provider() -> SkillsProvider | None:
    """Wire SKILL.md playbooks via MAF's progressive-disclosure provider.

    Returns None if the skills directory is missing or empty so the
    agent stays runnable with context_providers=[] instead of crashing
    at startup on a corrupt or absent skill folder.
    """
    skills_dir = Path(__file__).parent / "skills"
    if not skills_dir.exists():
        log.warning("Skills directory missing at %s; SkillsProvider disabled.", skills_dir)
        return None
    skill_subdirs = [
        d for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
    ]
    if not skill_subdirs:
        log.warning("No SKILL.md files found under %s; SkillsProvider disabled.", skills_dir)
        return None
    try:
        provider = SkillsProvider.from_paths(skills_dir)
        log.info(
            "SkillsProvider wired with %d skill(s): %s",
            len(skill_subdirs),
            ", ".join(sorted(d.name for d in skill_subdirs)),
        )
        return provider
    except Exception as exc:  # never crash on a corrupt skill folder
        log.warning("SkillsProvider init failed (%s); falling back to no-op.", exc)
        return None


def _load_instructions() -> str:
    """Base prompt + SPEC-derived constants ONLY. Skills are NOT concatenated
    here — they flow through SkillsProvider via context_providers."""
    base = Path(__file__).parent
    parts: list[str] = []
    parts.append((base / "copilot-instructions.md").read_text(encoding="utf-8"))
    config_path = base / "config" / "<process>.json"
    if config_path.exists():
        parts.append(
            "\n\n---\n\n# Runtime configuration\n\n"
            "These thresholds, lists, and templates are SPEC-derived constants. "
            "Honour them in your behaviour:\n\n```json\n"
            + config_path.read_text(encoding="utf-8")
            + "\n```\n"
        )
    return "\n".join(parts)


client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["MODEL_DEPLOYMENT_NAME"],
    credential=DefaultAzureCredential(),
)

skills_provider = _build_skills_provider()
context_providers = [skills_provider] if skills_provider is not None else []

agent = Agent(
    client=client,
    instructions=_load_instructions(),       # base + config ONLY (NOT skills)
    tools=[my_tool, mcp_tool],
    context_providers=context_providers,     # ← progressive skill loading
    default_options={"store": False},
)
ResponsesHostServer(agent).run()
```

**Constructor variants.** Both work and are equivalent:
- `SkillsProvider.from_paths(skills_dir)` — classmethod, the form used in
  production hosted agents. Use this.
- `SkillsProvider(skill_paths=skills_dir)` — keyword constructor shown in
  the official docs. Same outcome.

The provider searches up to two levels deep, so `skills/<name>/SKILL.md`
and `skills/<group>/<name>/SKILL.md` layouts are both auto-discovered.

**Per-query cost.** `SkillsProvider` adds **+1 `load_skill` tool call per
skill the agent activates per query** (typically 1-3 per query). This is
**NOT** the 20-34-internal-call overhead seen on `CopilotClient` runs —
that overhead lives in `CopilotClient` itself and is unrelated to
`SkillsProvider`.

**Quantified benefits** (from production MAF deployments):
- **~75% token saving** on the static prompt vs. concatenating all
  `SKILL.md` bodies into instructions.
- **Per-skill App Insights telemetry** — every `load_skill(name)` is a
  traceable tool-call span, so routing analysis (which skills get used?
  which never load? which load on the wrong intent?) is free.

#### Legacy alternative — inline `_load_skills()` concat

The pre-`SkillsProvider` pattern: read every `skills/*/SKILL.md` at
startup and append the bodies to the system prompt. Still supported,
still works, occasionally still the right choice.

```python
def _load_skills() -> str:
    chunks: list[str] = []
    skills_dir = Path(__file__).parent / "skills"
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        chunks.append(
            f"\n\n---\n\n# Skill: {skill_file.parent.name}\n\n"
            + skill_file.read_text(encoding="utf-8")
        )
    return "".join(chunks)


def _load_instructions_legacy() -> str:
    base = (Path(__file__).parent / "copilot-instructions.md").read_text(encoding="utf-8")
    return f"{base}\n\n{_load_skills()}"


agent = Agent(
    client=client,
    instructions=_load_instructions_legacy(),   # everything baked into the prompt
    tools=[my_tool, mcp_tool],
    # context_providers omitted — skills already in instructions
    default_options={"store": False},
)
```

#### When to choose which

| | `SkillsProvider` (recommended) | `_load_skills()` concat (legacy) |
|---|---|---|
| Per-query overhead | +1 `load_skill` per skill loaded (1-3/query typical) | None |
| Static prompt size | ~100 tokens/skill advertised | Full SKILL.md bodies always present |
| Total skill content >5 KB | ✅ recommended | ⚠️ blows up context budget every turn |
| Strict latency budget (sub-2s tools) | ⚠️ adds `load_skill` round-trip | ✅ faster cold path |
| Per-skill usage telemetry | ✅ free (every `load_skill` is a span) | ❌ invisible |
| New PoCs | ✅ default | only if total skill content is small (<5 KB) |
| Mixing both | ❌ never — double-counts every skill body | n/a |

#### Centralizing skills via the Foundry Skills REST API

The patterns above all assume `SKILL.md` files live in the agent's source
tree. If multiple Hosted agents in the same project need to share a
canonical set of `SKILL.md` files (without each repo carrying its own
copy), publish them to the project-level **Foundry Skills** store
(`{project}/skills`) and consume them via either:

- **Build-time bundle** — `azd predeploy` hook downloads all published
  skills into `src/skills/` so the standard `SkillsProvider(skill_paths=…)`
  above keeps working unchanged.
- **Runtime fetch** — `SkillsProvider(source=FoundrySkillsSource(…))` with
  a custom `SkillsSource` that pulls from the REST API on session create.

See **`foundry-skill-catalog`** for the REST surface, the silent
JSON-mode-is-write-only trap, and the verified-working `FoundrySkillsSource`
adapter.

### Multi-Agent: Calling Other Foundry Agents as Tools

Use the **client-swap pattern** to connect to existing prompt/hosted agents in the same project:

```python
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.ai.projects.aio import AIProjectClient  # MUST be .aio (async)!
from azure.identity import DefaultAzureCredential

project_client = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
    allow_preview=True,  # REQUIRED for agent_name parameter
)

# Create FoundryChatClient, swap its OpenAI client to the agent-bound one
sub_client = FoundryChatClient(project_client=project_client, model="gpt-5.4-mini")
sub_client.client = project_client.get_openai_client(agent_name="my-sub-agent")

sub_agent = Agent(name="my-sub-agent", client=sub_client)

orchestrator = Agent(
    client=FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model="gpt-5.4-mini",
        credential=DefaultAzureCredential(),
    ),
    instructions="You orchestrate sub-agents.",
    tools=[sub_agent.as_tool()],
    default_options={"store": False},
)

ResponsesHostServer(orchestrator).run()
```

**Critical rules:**
- `AIProjectClient` MUST be from `azure.ai.projects.aio` (async) — the sync version returns a sync `OpenAI` client that **silently fails** inside `FoundryChatClient`
- `allow_preview=True` is REQUIRED for `agent_name` to work
- `FoundryChatClient` does NOT accept `agent_name`/`agent_version` — use the client-swap pattern

> **⚠️ DO NOT use `FoundryAgent` for sub-agent delegation.** `FoundryAgent` (v1.1.1) internally
> uses `extra_body={"agent_reference": ...}` which is the OLD initial preview pattern.
> It silently fails in the refreshed preview — tool calls return "Function failed."
> Use the client-swap pattern above instead.

### MCP Tools via FoundryChatClient

> **🟡 Status: bug-009/014 FIXED in `agent-framework-core` 1.3.0
> (released 2026-05-07 via [PR #5581](https://github.com/microsoft/agent-framework/pull/5581),
> merged 2026-04-30).** The fix prefers plain string entries, then
> `.text` attribute, then `entry["text"]` for `Mapping` entries, then
> `json.dumps(output, default=str)` final fallback — sidestepping the
> `str()` fallback that produced `[<Content object at 0x...>]` Python
> reprs from the canonical MCP raw-JSON shape. Companion fix
> [PR #5687](https://github.com/microsoft/agent-framework/pull/5687)
> (also in 1.3.0) stops `MCPStreamableHTTPTool` from swallowing
> `asyncio.CancelledError` when the MCP server is unreachable.
>
> **Both surfaces are now valid in 1.3.0+:**
> - `client.get_mcp_tool()` — concise, hosted MCP shape, **STATIC `headers: dict[str, str]`** only
>   (no `header_provider` callback — bearer tokens expire after ~1h, so
>   this path is **not viable for AAD-bearer-authenticated MCP servers**
>   like AI Search KB MCP unless headers can be pinned for the agent's
>   lifetime; fine for API-key auth or unauthenticated MCP)
> - `MCPStreamableHTTPTool + parse_tool_results` — verbose,
>   client-side, supports `header_provider: Callable[[dict], dict[str, str]]`
>   for per-call token refresh — **REQUIRED for AAD-bearer auth**
>
> Choose `MCPStreamableHTTPTool` whenever the MCP server uses
> short-lived bearer tokens or you need per-request header logic; choose
> `client.get_mcp_tool()` for static-header MCP servers when you want
> the hosted MCP execution model.
>
> **Pre-1.3.0 versions (1.1.x, 1.2.x) still have the bug.** If pinned
> to an older release, stay on `MCPStreamableHTTPTool + parse_tool_results`.

```python
# ✅ OK in 1.3.0+ (was buggy in 1.1.x/1.2.x); STATIC headers only
mcp_tool = client.get_mcp_tool(
    name="my-mcp",
    url="https://my-mcp-server.azurecontainerapps.io/mcp",
    headers={"Authorization": f"Bearer {long_lived_or_api_key}"},
    approval_mode="never_require",
)
agent = Agent(client=client, tools=[my_tool, mcp_tool], ...)
```

> **URL must be a valid URI** (starts with `http://` or `https://`). Unresolved
> `${ENV_VAR}` placeholders that expand to empty strings cause `invalid_payload`
> errors at runtime.

### MCP Tools — recommended pattern (`MCPStreamableHTTPTool` + `parse_tool_results`)

Use `MCPStreamableHTTPTool` directly with a custom `parse_tool_results`
callback that extracts the `TextContent.text` payload from the MCP
`CallToolResult` and surfaces it to the model as plain JSON. This
sidesteps `FoundryChatClient.get_mcp_tool()` entirely and avoids the
`[<Content object>]` repr leak.

**Worked example** — validated in recent pilots, running on a
10-tool MCP server with `gpt-5.4-mini`:

```python
import json
from agent_framework import Agent, MCPStreamableHTTPTool, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential


def _mcp_text_extractor(result):
    """Convert an MCP CallToolResult into the plain JSON string the model expects.

    Without this callback, agent_framework's default rendering of MCP results
    leaks the Python repr of `[<Content object>]` into the model's view, which
    gpt-5.4-mini reads as a tool failure. We surface the first TextContent
    payload (which the MCP server returns as `json.dumps(...)`) verbatim.
    """
    if getattr(result, "isError", False):
        return json.dumps({
            "error": "mcp_tool_error",
            "content": [str(c) for c in (result.content or [])],
        })
    for c in result.content or []:
        text = getattr(c, "text", None)
        if isinstance(text, str) and text:
            return text
    sc = getattr(result, "structuredContent", None)
    if sc is not None:
        return json.dumps(sc, default=str)
    return json.dumps({"_empty": True})


client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["MODEL_DEPLOYMENT_NAME"],
    credential=DefaultAzureCredential(),
)

mcp_tool = MCPStreamableHTTPTool(
    name="<process>_mcp",
    url=f"https://{os.environ['MCP_SERVER_FQDN']}/mcp",
    approval_mode="never_require",
    parse_tool_results=_mcp_text_extractor,   # ⚠️ THE FIX — opts out of default rendering
    request_timeout=60,
)

agent = Agent(client=client, tools=[my_local_tool, mcp_tool], ...)
```

**Why this works:**
- `MCPStreamableHTTPTool` is the lower-level MAF primitive that
  `client.get_mcp_tool()` wraps — bypassing the wrapper avoids the
  buggy renderer.
- `parse_tool_results` is invoked by MAF on every tool result before
  it's rendered into the model's history; returning a plain string
  makes that string what the model sees verbatim.
- The MCP server should return `json.dumps(...)` from each tool
  handler (FastMCP wraps it as a single `TextContent`); the extractor
  unwraps that back to the JSON string.

**When pure-compute logic doesn't need to be on the MCP server,
inline it as `@tool`.** The MCP-vs-`@tool` rule from recent pilots:
- **MCP server** for any tool with I/O (DB lookups, file reads,
  external API calls).
- **Inline `@tool`** for pure computation (date math, formatting,
  validation) — cheaper round-trip, no HTTP hop.

**Probe to verify the fix is in place** — dump the raw
`custom_tool_call_output` from a real Foundry trace; the `output`
field should be a plain JSON string (e.g. `{"case_id":"...","status":"..."}`),
NOT `[<agent_framework._types.Content object at 0x...>]`. Your
process repo should ship `tests/probe_mcp_output.py` for this.

> **Status note.** As of `agent-framework-core` 1.3.0 (2026-05-07,
> [PR #5581](https://github.com/microsoft/agent-framework/pull/5581)),
> `client.get_mcp_tool()` is also bug-free — but only supports STATIC
> `headers` (no per-call refresh callback), so it cannot be used for
> AAD-bearer-authenticated MCP servers like AI Search KB MCP. The
> `MCPStreamableHTTPTool + parse_tool_results` pattern remains the
> canonical choice for any MCP server that needs short-lived tokens
> via `header_provider`. Captured from recent PoC retrospectives.

### MCP with per-call AAD bearer (`header_provider`)

> **⚠️ Bootstrap caveat (CRITICAL — read first).** `header_provider=`
> only covers `call_tool()` requests, NOT the MCP bootstrap exchange
> (`initialize` + `tools/list` issued by `_ensure_connected`). For
> AAD-secured MCP endpoints that require auth on bootstrap (Azure AI
> Search Knowledge Base MCP, anything behind PMI), `header_provider=`
> fails with **401** BEFORE the first `call_tool` ever fires — the
> `_mcp_call_headers` ContextVar that `header_provider` writes to is
> only set inside `call_tool()` (`agent_framework/_mcp.py` ~line 1589).
> On hosted agents the symptom is every Responses request returning
> `server_error` with no useful log signal. **Use `httpx.AsyncClient(auth=httpx.Auth)`
> via `http_client=` instead** (companion example below) — see
> `foundry-iq` SKILL § "KB access from a hosted MAF agent — three
> routes" → Route B for the canonical pattern.

For MCP servers backed by Azure services that authenticate with
Microsoft Entra ID **where bootstrap does NOT require auth** (e.g.
some custom MCP servers that auth-gate per-tool but allow open
discovery), use the `header_provider` callback to mint a fresh
bearer token per tool invocation. Per the SDK's own docstring, the
callback "receives the runtime keyword arguments" — a generic
`dict[str, Any]` populated by MAF at tool-invoke time — and returns
a `dict[str, str]` of HTTP headers attached to every outbound request
during that tool call.

```python
import os
from agent_framework import MCPStreamableHTTPTool
from azure.identity import DefaultAzureCredential

# Module-level singleton so the in-memory token cache is reused across
# MCP calls; get_token() returns a cached token if it's valid for >= ~5 min
_credential: DefaultAzureCredential | None = None

def _get_credential() -> DefaultAzureCredential:
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential

def _bearer_headers(_kwargs: dict) -> dict[str, str]:
    """MAF header_provider — mints a fresh AAD bearer per MCP call.
    Cached by the credential layer; refreshed automatically on expiry.
    """
    tok = _get_credential().get_token("https://search.azure.com/.default")
    return {"Authorization": f"Bearer {tok.token}"}

kb_mcp = MCPStreamableHTTPTool(
    name="my_kb_mcp",
    url=f"{os.environ['AI_SEARCH_ENDPOINT']}/knowledgebases/<kb-name>/mcp"
        f"?api-version=2025-11-01-preview",
    approval_mode="never_require",
    parse_tool_results=_mcp_text_extractor,   # same extractor as above
    header_provider=_bearer_headers,           # 🔑 per-call refresh
    request_timeout=60,
)
```

#### Companion: `httpx.Auth` for AAD-bootstrap-required MCPs (CANONICAL)

When the MCP endpoint authenticates `initialize` / `tools/list` (any
Azure AI Search KB MCP, any PMI-protected MCP), supply auth at the
`httpx` transport layer instead — `httpx.Auth.auth_flow()` is invoked
on EVERY outbound request including bootstrap, so the agent's MCP
handshake completes successfully:

```python
import os, httpx
from agent_framework import MCPStreamableHTTPTool
from azure.identity import DefaultAzureCredential

_credential = DefaultAzureCredential()

class _AADBearerAuth(httpx.Auth):
    """Mints AAD bearer per request — covers MCP bootstrap, not just call_tool."""
    def __init__(self, scope: str) -> None:
        self.scope = scope
    def auth_flow(self, request: httpx.Request):
        token = _credential.get_token(self.scope).token
        request.headers["Authorization"] = f"Bearer {token}"
        yield request

_http = httpx.AsyncClient(
    auth=_AADBearerAuth("https://search.azure.com/.default"),
    timeout=120.0,
)

kb_mcp = MCPStreamableHTTPTool(
    name="my_kb_mcp",
    url=(f"{os.environ['AI_SEARCH_ENDPOINT']}/knowledgebases/<kb-name>/mcp"
         f"?api-version=2025-11-01-preview"),
    http_client=_http,            # 🔑 auth covers BOOTSTRAP, not just call_tool
    parse_tool_results=_mcp_text_extractor,
    load_prompts=False,           # avoid prompts/list 500s on KB MCP
    request_timeout=120,
)
```

> **Do NOT combine `header_provider=` AND `http_client=` (with auth).**
> Pick one. `httpx.Auth` is canonical for AAD-secured Azure MCP
> endpoints; `header_provider=` is appropriate only for tool-call-only
> headers (e.g. per-call correlation IDs that don't need to cover
> bootstrap).

> **⚠️ MCP `ping` trap on Foundry-hosted MCP servers.** MAF's
> `MCPStreamableHTTPTool._ensure_connected()` issues an MCP `ping`
> request during agent registration. **The Foundry Toolbox MCP
> endpoint is documented to return HTTP 500 on `ping`** because the
> server doesn't implement the optional MCP `ping` method (per the
> Toolbox docs). The same failure mode has been observed on direct
> KB MCP wiring (`/knowledgebases/<n>/mcp`) but is not yet documented
> upstream — treat as suspected, not confirmed, until you've reproduced
> it on your tenant. When the trap fires, agent registration fails and
> every invoke returns `server_error` from the responses endpoint with
> no useful log signal. Workarounds: (a) override
> `MCPStreamableHTTPTool._ensure_connected` with a no-op subclass to
> skip the ping, or (b) use the static-headers `client.get_mcp_tool()`
> shape if your MCP doesn't need per-call AAD refresh.

### File Generation (@tool pattern)

Agents can generate downloadable files (XLSX, PDF, CSV, HTML) using a custom `@tool`.
Files are written to `$HOME` inside the container; the hosting platform exposes them
via the session files API, and the Teams bot delivers them via FileConsentCard
(see [foundry-teams-bot skill](#sending-files-to-teams)).

```python
@tool(approval_mode="never_require")
def save_report(
    filename: Annotated[str, Field(description="Filename (e.g. report.xlsx, summary.pdf)")],
    content: Annotated[str, Field(description="File content: CSV text, JSON for XLSX, HTML for pdf")],
    format: Annotated[str, Field(description="Format: csv, xlsx, html, or pdf")] = "csv",
) -> str:
    """Save a report file that the user can download."""
    from pathlib import Path
    home = Path.home()
    filepath = home / filename

    if format == "xlsx":
        import openpyxl
        import json as _json
        data = _json.loads(content)
        wb = openpyxl.Workbook()
        ws = wb.active
        if data and isinstance(data, list):
            ws.append(list(data[0].keys()))
            for row in data:
                ws.append(list(row.values()))
        wb.save(str(filepath))
    elif format == "pdf":
        from fpdf import FPDF
        import re
        # Strip CSS but keep structural HTML for write_html()
        cleaned = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
        cleaned = re.sub(r'\s+(class|style|id)="[^"]*"', "", cleaned)
        cleaned = cleaned.replace("<table", '<table border="1" width="100%"')
        cleaned = cleaned.replace("<th", '<th bgcolor="#d0d0d0"')
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", "", 10)
        pdf.write_html(cleaned)
        pdf.output(str(filepath))
    else:
        filepath.write_text(content, encoding="utf-8")

    return f"Report saved: {filename} ({filepath.stat().st_size:,} bytes). User can download it."
```

**Required dependencies** in `pyproject.toml`:

```toml
dependencies = [
    # ... agent-framework packages ...
    "openpyxl>=3.1.0",   # XLSX generation
    "fpdf2>=2.8.0",      # PDF generation (pure Python, no system deps)
]
```

**Instructions directive** — add to `copilot-instructions.md`:

```markdown
## Report Generation

You have a `save_report` tool for generating downloadable files:
- **XLSX**: JSON array of objects → `save_report(filename="report.xlsx", content=json_data, format="xlsx")`
- **PDF**: HTML content → `save_report(filename="report.pdf", content=html, format="pdf")`
- **CSV**: Raw CSV text → `save_report(filename="report.csv", content=csv, format="csv")`
- **HTML**: HTML content → `save_report(filename="report.html", content=html, format="html")`
```

**Key points:**
- `fpdf2` is pure Python — no Playwright, wkhtmltopdf, or headless Chrome needed
- `fpdf2.write_html()` renders HTML tables with borders and header highlighting
- Files written to `Path.home()` are automatically available via the session files API
- The bot captures `agent_session_id` from the `response.completed` event to locate files
- Wrap each format in try/except to return a clean error if generation fails

> **Validated** — XLSX and PDF file delivery tested end-to-end in recent
> file-delivery pilots. FileConsentCard renders clickable OneDrive cards in Teams.

---

## Dependencies (pyproject.toml)

```toml
[project]
name = "my-agent"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "agent-framework-core~=1.4.0",
    "agent-framework-foundry~=1.4.0",
    "agent-framework-foundry-hosting==1.0.0a260514",
    "azure-ai-projects>=2.1.0",
    "azure-identity>=1.19.0,<1.26.0a0",
    "mcp>=1.10.0",
    "python-dotenv>=1.0.0",
    # Add these if using save_report file generation:
    # "openpyxl>=3.1.0",   # XLSX
    # "fpdf2>=2.8.0",      # PDF (pure Python)
]

[tool.uv]
required-environments = ["sys_platform == 'linux' and platform_machine == 'x86_64'"]
prerelease = "if-necessary-or-explicit"

[tool.setuptools]
packages = []
```

**Do NOT use `agent-framework>=1.4.0` as a meta-package.** The meta-package's transitive
resolution is non-deterministic across uv versions. Pin `agent-framework-core~=1.4.0` and
`agent-framework-foundry~=1.4.0` (PEP 440 compatible-release caps) instead, and pin the
alpha hosting package by exact version `==1.0.0a260514` — pre-release cap math doesn't
survive across alpha boundaries, so `~=` would silently jump to a later alpha. Verified
working on linux/amd64 as the current reference shape, superseding prior 1.3.0 pinning
guidance that became fragile once Azure renamed the Foundry data-plane role and changed
the SDK's token-scope audience (see [§ MAF 1.4.0 breaking changes](#maf-140-breaking-changes-may-2026)).

**Mandatory adjacent rules** (lessons from recent dependency-resolution retrospectives):
- **Drop** any explicit `azure-ai-agentserver-responses` line — `agent-framework-foundry-hosting`
  pins the right transitive itself; declaring it explicitly causes uv to resolve a stack that
  passes install but crashes at first invocation with opaque `server_error/model:""`.
- **Add** explicit `mcp>=1.10.0` whenever using `MCPStreamableHTTPTool`. `agent-framework-core 1.4.0`
  does NOT auto-pull it.
- **Include** `[tool.setuptools] packages = []` for clean uv resolution.

**`prerelease = "if-necessary-or-explicit"` is correct** — packages with explicit
prerelease markers (e.g. `==1.0.0a260514`) resolve to prereleases; everything else
stays GA. Do NOT use `"allow"` — it pulls beta azure-identity 1.26.0b2.

### Dependency Chain (verified on PyPI)

| Package | Version | Type | Pulls in |
|---------|---------|------|----------|
| `agent-framework-core` | 1.4.0 | ✅ Stable | pydantic, opentelemetry-api |
| `agent-framework-foundry` | 1.4.0 | ✅ Stable | core, openai, azure-ai-projects |
| `agent-framework-foundry-hosting` | 1.0.0a260514 | ⚠️ Alpha | agentserver-core==2.0.0b2, agentserver-responses==1.0.0b4 |
| `mcp` | ≥1.10.0 | ✅ Stable | Required by MCPStreamableHTTPTool — NOT auto-pulled by core 1.4.0 |
| `azure-identity` | 1.25.3 | ✅ Stable (pinned `<1.26.0a0` to avoid beta) | |

No `override-dependencies` needed — the hosting package pins its own transitive deps.

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/
COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project && rm -rf /root/.cache
COPY container.py .
COPY copilot-instructions.md .
EXPOSE 8088
CMD [".venv/bin/python", "container.py"]
```

- Port 8088 is the standard Foundry agent port
- `--platform linux/amd64` only needed for local builds
- `azd deploy` builds remotely via ACR — no local Docker needed

---

## agent.yaml (ContainerAgent Schema)

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/microsoft/AgentSchema/refs/heads/main/schemas/v1.0/ContainerAgent.yaml

name: my-agent
description: My agent description
kind: hosted
protocols:
  - protocol: responses
    version: 1.0.0
environment_variables:
  - name: MODEL_DEPLOYMENT_NAME
    value: gpt-5.4   # default for production; use gpt-5.4-mini only for trivial 1-2-step flows
resources:
  cpu: "1"
  memory: 2Gi
```

### Critical Rules

| Rule | Why |
|------|-----|
| `kind: hosted` at **top level** | ContainerAgent schema — NOT nested under `template:` |
| Protocol version `1.0.0` | Semver format — NOT `"v1"` (old preview) |
| `resources: {cpu, memory}` flat object | NOT a YAML list `[{kind: model}]` |
| NO `FOUNDRY_PROJECT_ENDPOINT` | Reserved — platform injects it. All `FOUNDRY_*` and `AGENT_*` prefixed vars are reserved |
| NO `APPLICATIONINSIGHTS_CONNECTION_STRING` | Also reserved. Platform attempts to auto-inject from the account-level `AppInsights` connection — but auto-injection is **best-effort**, can silently fail (see Troubleshooting), and you CANNOT escape-hatch via `agent.yaml`. Use guarded `_init_telemetry()` in `container.py` so the agent survives the failure (see `foundry-observability` gap rows O-011 / O-012) |
| Model deployment in `azure.yaml` | NOT in agent.yaml — declared in `config.deployments` |

> **Two schemas exist — don't confuse them:**
> - `agent.yaml` → **ContainerAgent** schema (what `azd ai agent` extension reads)
> - `agent.manifest.yaml` → foundry-samples format (for sample repos, NOT azd)

---

## azure.yaml (azd ai agent Extension)

```yaml
name: my-project

requiredVersions:
  extensions:
    azure.ai.agents: ">=0.1.25-preview"

services:
  my-agent:
    project: .
    host: azure.ai.agent
    language: docker
    docker:
      remoteBuild: true
    config:
      container:
        resources:
          cpu: "1"
          memory: 2Gi
      deployments:
        - model:
            format: OpenAI
            name: gpt-5.4
            version: "2026-03-05"
          name: gpt-5.4
          sku:
            capacity: 50
            name: GlobalStandard

infra:
  provider: bicep
  path: ./infra
```

### Model Version Lookup

| Model | Version |
|-------|---------|
| `gpt-5.4` | `2026-03-05` |
| `gpt-5.4-mini` | `2026-03-17` |
| `gpt-5.4-nano` | `2026-03-17` |
| `gpt-5.3-codex` | `2026-02-24` |
| `gpt-5.2` | `2025-12-11` |
| `gpt-5` | `2025-08-07` |
| `gpt-5-mini` | `2025-08-07` |
| `gpt-4.1` | `2025-04-14` |
| `gpt-4.1-mini` | `2025-04-14` |

Verify with: `az cognitiveservices account list-models --resource-group <rg> --name <account> -o table`

---

## Bicep Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `ENABLE_HOSTED_AGENTS` | `false` → set `true` by extension | Enables hosted agent infrastructure |
| `ENABLE_CAPABILITY_HOST` | **`false`** ⚠️ | **MUST be false.** Capability hosts were removed in refreshed preview |
| `ENABLE_MONITORING` | `true` | Application Insights + Log Analytics |

---

## Identity & RBAC

### Agent Identities

Each hosted agent gets **two Entra identities** at deploy time:

| Identity | Field | Purpose |
|----------|-------|---------|
| Instance identity | `instance_identity.principal_id` | Agent's service principal for runtime |
| Blueprint identity | `blueprint.principal_id` | Platform internal operations |

View them with `azd ai agent show`.

> **⚠️ ServiceIdentity Cosmos limitation.** The instance identity has `servicePrincipalType=ServiceIdentity`,
> which the Cosmos DB data-plane RBAC engine **does not accept** — direct
> role assignments fail with `unsupported type [Unfamiliar]`. The same
> holds for Azure AI Search data-plane in some configurations.
> **Workaround:** route Cosmos / Search access through an MCP server
> backed by a **separate User-Assigned Managed Identity (UAMI)**. Grant
> the data-plane role to that UAMI, give the agent only the MCP tool;
> the agent never touches the data plane directly. Captured from
> recent PoC retrospectives.

### Required Role Assignments

**Deploying user:**

| Role | Scope | Why |
|------|-------|-----|
| `Azure AI Project Manager` | Foundry project | Create agents + auto-assign RBAC to agent identity |
| `Contributor` | Resource group | Provision Azure resources |

**Agent identities (both instance + blueprint):**

| Role | Scope | Why |
|------|-------|-----|
| `Foundry User` (GUID `53ca6127-…`) | Foundry account | Model inference |
| `Foundry User` (GUID `53ca6127-…`) | Foundry project | Storage, history, project-scoped APIs |

**Project managed identity (system-assigned on the Foundry account):**

| Role | Scope | Why |
|------|-------|-----|
| `Foundry User` (GUID `53ca6127-…`) | Foundry account | Model inference via project endpoint |
| `Container Registry Repository Reader` | ACR | Pull container images |

**Workload UAMI (user-assigned identity attached to companion services — agents service, ACA jobs, bot, MCP servers):**

| Role | Scope | Why |
|------|-------|-----|
| `Foundry User` (GUID `53ca6127-…`) | Foundry **account** (CognitiveServices) | Data-plane access to call models / agents. **`Foundry Account Owner` no longer implies data-plane access** — you MUST grant `Foundry User` on the account directly, even if the UAMI already has `Foundry Account Owner` for control-plane work. Verified missing-then-added in May 2026 hosted-agent debug session |

> **About the GUID.** `53ca6127-db72-4b80-b1b0-d745d6d5456d` is the
> built-in role definition for what Azure now calls **Foundry User**
> (formerly **Azure AI User**). The GUID is unchanged across the rename
> — `az role assignment create --role 53ca6127-db72-4b80-b1b0-d745d6d5456d`
> is the safest call-site form because it survives further display-name
> rotations.

### Auto-Assignment via postdeploy Hook

The `azd ai agent` extension's postdeploy hook **automatically assigns** `Foundry User`
(GUID `53ca6127-db72-4b80-b1b0-d745d6d5456d`) to the agent identity. For this to work, you need:

1. `Azure AI Project Manager` role on the Foundry project
2. `AZURE_TENANT_ID` set in azd env: `azd env set AZURE_TENANT_ID <tenant-id>`

Without both, postdeploy fails silently and the agent gets 401 at runtime.

> **Companion-service identities are NOT auto-assigned.** The postdeploy
> hook only covers the hosted-agent identities. If you have a separate
> agents service, ACA job, bot, or MCP server using its own UAMI, you
> MUST grant `Foundry User` on the Foundry account to that UAMI yourself
> (Bicep `roleAssignments` block — see the row above).

### Manual RBAC Assignment (if postdeploy failed)

```bash
# Get agent identities
azd ai agent show
# → instance_identity.principal_id and blueprint.principal_id

ACCT="/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>"
PROJ="$ACCT/projects/<project>"

# Pin by GUID — survives display-name rotations (e.g. "Azure AI User" → "Foundry User" in May 2026)
FOUNDRY_USER_ROLE=53ca6127-db72-4b80-b1b0-d745d6d5456d

# For EACH principal ID:
az role assignment create --assignee <PRINCIPAL_ID> --role "$FOUNDRY_USER_ROLE" --scope $ACCT
az role assignment create --assignee <PRINCIPAL_ID> --role "$FOUNDRY_USER_ROLE" --scope $PROJ
```

> RBAC propagation takes **5-15 minutes** for new service principals. If still failing,
> redeploy (`azd deploy <service>`) to force a new container session.

---

## Deployment Flow

```
azd up
  ├── provision → Bicep (Foundry account, project, ACR, monitoring)
  ├── postprovision hooks (if any)
  ├── azd ai agent extension →
  │   ├── Deploy model (from azure.yaml config.deployments)
  │   ├── Build container remotely via ACR
  │   ├── Create hosted agent version
  │   └── postdeploy → auto-assign Foundry User (53ca6127) to agent identity
  └── deploy other services (bot ACA, etc.)
```

### Invocation

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

project = AIProjectClient(
    endpoint="<project_endpoint>",
    credential=DefaultAzureCredential(),
    allow_preview=True,  # REQUIRED for agent_name
)
oai = project.get_openai_client(agent_name="my-agent")
response = oai.responses.create(input="Hello!", stream=False)
print(response.output_text)
```

Or via CLI: `azd ai agent invoke "Hello!"`

Or via REST (requires `Foundry-Features: HostedAgents=V1Preview` header):
```
POST {project_endpoint}/agents/{name}/endpoint/protocols/openai/responses
```

### Compute Lifecycle

- **Automatic** — no manual start/stop
- Provisions on first request
- Deprovisions after 15 minutes of inactivity
- No replica management

---

## Region Availability

Not all regions support hosted agents. If you get `"The requested experience is
not available for this subscription"`, try a different region.

**Known working (April 2026):** `northcentralus`, `eastus`, `swedencentral`, `westus`
**Known failing:** `eastus2`

Check [Region availability](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents#region-availability) for current list.

---

## Gateway throttle finding (preview)

The Foundry hosted-agent gateway has an undocumented preview-time
throttle: **~6 sustained sequential invocations per warm period**
before sticky `internal_server_error` responses with a **5–10 minute
recovery window**. Validated in May 2026 against a real pilot agent
across 3 successive eval runs.

### Detection signature

Look for ALL of these together:

* Cold-start: first 1–2 warmup pings return `server_error` in 5–10s
  before the platform brings a replica up
* Warm phase: exactly **5–6 sequential invocations** answer in 30–60s
  each (real tool work) with normal latency
* Throttle phase: from invocation 7–9 onwards, every call returns
  `internal_server_error` (or `server_error` / `model:""`) in **5–10s
  consistent latency** — too fast for real tool work, too slow for a
  4xx routing failure
* Recovery: **5–10 min idle restores normal operation** (no manual
  restart, no replica scale, no env change required)

### What's NOT the cause

Each lever was independently bumped in a controlled test (single pilot
agent, 30-scenario eval) and the boundary did NOT move:

| Lever | Before | After | Effect on 6-call boundary |
|---|---|---|---|
| Container CPU | 0.25 | 1.0 | none |
| Container memory | 0.5Gi | 2Gi | none |
| Replicas | 1 (no scale) | min=1 max=3 | none |
| Model TPM | 50K | 300K | +1 answered scenario only |
| Pacing between invocations | 5s | 30s | none |
| Invocation retries | 1 | 3 | retry burst makes it WORSE |

The boundary is **gateway-side, not container-side**. Container restart,
replica swap, and `azd deploy agent` all leave the throttle window
unchanged.

### Mitigation (eval / workshop posture)

* **Run evals in 5-scenario batches** with 5-minute cooldown between
  batches. Pre-warm each batch with a throwaway invocation. See
  `foundry-evals` SKILL § "Warmup retry loop, not single-shot" and
  § "Resume-after-cooldown".
* **Move tool work to INGEST time** where feasible — visual extraction,
  document parsing, embedding generation should run in a one-shot
  ACA Job or postprovision script, not inside the agent's tool budget.
  See `foundry-doc-vision-speech` SKILL § Pattern X for the ingest-time
  vision pattern that explicitly sidesteps this throttle.
* **Sample, don't burst** for continuous-eval — see `foundry-evals`
  SKILL § Continuous Evaluation Loop, Plan A `EvaluationRule` with
  `event_type=SAMPLED` (not `RESPONSE_COMPLETED`).

### Production posture (not just demo)

* **Target architecture for production traffic at scale: APIM gateway
  in front of the hosted agent**, with retry + queue semantics in the
  gateway (not in every client). The hosted-agent runtime itself is the
  bottleneck; horizontally scaling the agent container does NOT bypass
  the throttle.
* **File a Foundry support ticket** with detection-signature evidence
  if the throttle blocks your production sizing — preview limits are
  often raised on request once a pattern is documented end-to-end.

### Diagnosis blocker

Confirming root cause is hard because the throttle window typically
coincides with **zero `AppExceptions` / `AppTraces` reaching App
Insights** — the gateway absorbs the failed requests and never emits
container-side telemetry for them. Ensure your `_init_telemetry()`
guard is in place (see § Troubleshooting → AppInsights row + `gap O-011`
in `foundry-observability`) BEFORE investigating; otherwise you're
flying blind.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `FOUNDRY_PROJECT_ENDPOINT is reserved` | Declared in agent.yaml env vars | Remove it — platform injects automatically |
| `AGENT_* env var is reserved` | All `FOUNDRY_*` and `AGENT_*` prefixed vars are reserved | Use a different prefix (e.g. `TL_SUB_AGENTS`) |
| `session_not_ready` (424) | Container crashed before readiness probe | Check logstream: `curl ...sessions/{sid}:logstream`. Common causes: import error, sync/async mismatch, missing dep |
| Sub-agent tool calls return "Function failed" | `FoundryAgent` uses old `agent_reference` pattern | Use the client-swap pattern: `sub_client.client = project_client.get_openai_client(agent_name=...)` |
| Sub-agent calls silently fail (empty output) | `AIProjectClient` imported from sync (`azure.ai.projects`) | MUST use `azure.ai.projects.aio` — sync `get_openai_client` returns sync OpenAI which fails in async `FoundryChatClient` |
| `PermissionDenied: Principal does not have access` | Agent identity missing `Foundry User` (GUID `53ca6127-…`, formerly "Azure AI User") on account AND project | Assign on both scopes; `_assign_agent_identity_roles()` does this automatically. If your role-assignment script still passes `--role "Azure AI User"`, replace with the GUID `53ca6127-db72-4b80-b1b0-d745d6d5456d` to survive the May 2026 display-name rename |
| **`401 Unauthorized` on every Responses call after `azd deploy`; RBAC visibly correct (`Foundry User` on both scopes)** | Orchestrator image still on `agent-framework-core` ≤ 1.3.x — requests the OLD `cognitiveservices.azure.com` token scope, which the post-rename Foundry data plane rejects. Most commonly happens to agent versions pinned by `sha256@…` digest (digest is frozen at the 1.3.x build) while a sibling agent on the same project that uses `:latest` works fine because ACR re-resolved it to a fresh 1.4.0 layer | Upgrade orchestrator `pyproject.toml` to `agent-framework-core~=1.4.0` + `agent-framework-foundry~=1.4.0` + `agent-framework-foundry-hosting==1.0.0a260514`, regenerate `uv.lock`, `az acr build` with BOTH `:latest` AND a date-pinned tag (`maf14-YYYYMMDDHHMM`), `azd deploy agents`, then re-import every agent version. See [§ MAF 1.4.0 breaking changes](#maf-140-breaking-changes-may-2026) for the full recipe |
| **`ImportError: cannot import name 'AzureOpenAIChatClient' from 'agent_framework.azure'`** after `pip install -U agent-framework-*` | `AzureOpenAIChatClient` was removed in `agent-framework-core` 1.4.0 (2026-05-14). Hits sidecars, agents service, eval judges — anywhere that talked directly to Azure OpenAI without going through `FoundryChatClient` | Swap to `from agent_framework.openai import OpenAIChatClient` and use `OpenAIChatClient(azure_endpoint=…, model=…, credential=DefaultAzureCredential())`. Drop the explicit `get_bearer_token_provider` / `ad_token_provider` — the SDK derives the right scope itself. See snippet in [§ MAF 1.4.0 breaking changes](#maf-140-breaking-changes-may-2026) |
| **Workload UAMI hits `Foundry User` 403 even with `Foundry Account Owner`** | Post-rename, **`Foundry Account Owner` no longer implies `Foundry User` data-plane access**. The owner role covers control-plane operations only; data-plane (model inference, agents endpoint) now requires `Foundry User` on the account explicitly | Add a Bicep `roleAssignments` block granting `Foundry User` (GUID `53ca6127-db72-4b80-b1b0-d745d6d5456d`) to the UAMI on the CognitiveServices account scope. See § Identity & RBAC "Workload UAMI" row |
| `Experience not available for this subscription` | Region doesn't support hosted agents, or `ENABLE_CAPABILITY_HOST=true` | Set `ENABLE_CAPABILITY_HOST=false`, try `northcentralus` |
| Eval items have empty responses | Concurrent eval requests overwhelm cold-start container | Use sequential eval with warm-up request first (see `run_evals()` in evals.py) |
| Agent skips evidence-gathering tools and emits hollow packets | gpt-5.4-mini tool-call discipline degrades on long instruction chains (10+ steps); model calls commit-tool before evidence is ready | Two complementary fixes: (1) switch `MODEL_DEPLOYMENT_NAME` to `gpt-5.4` (full); (2) make commit-tools refuse hollow inputs server-side via the validate-or-reject pattern in `foundry-mcp-aca`. Recent strict-smoke runs showed low reproducibility with mini + permissive MCP and high reproducibility with gpt-5.4 + validate-or-reject. |
| `Managed environment provisioning timed out` | CapabilityHost was manually created/deleted | Do NOT create CapabilityHosts — platform manages infrastructure automatically |
| `APPLICATIONINSIGHTS_CONNECTION_STRING is reserved` (HTTP 400 `invalid_request_error` at `create_version`) | Set in `agent.yaml` `environment_variables` OR `HostedAgentDefinition.environment_variables` (e.g. as escape-hatch when platform auto-injection silently failed) | Remove it. Cannot be escape-hatched. You MUST guard `configure_azure_monitor()` defensively in `container.py` instead — use `_init_telemetry()` from `foundry-observability` (gap O-011). Observed in hosted-agent validation |
| Agent traces not appearing in AppInsights | Agent identities lack `Monitoring Metrics Publisher` OR AppInsights connection missing on account | Assign RBAC to both identity principal IDs. Create `AppInsights` connection on the **account** (not project): category `AppInsights`, target = ARM resource ID, metadata `ApiType: Azure`. |
| **Hosted agent returns `server_error`/`model:""` on every smoke; AppIn 0 rows; `azd ai agent show` reports active** | `container.py` calls raw `configure_azure_monitor()` as the first line of `main()` with no try/except. When the platform fails to auto-inject `APPLICATIONINSIGHTS_CONNECTION_STRING` (e.g. AppIn account-level connection persisted with `credentials: null`), the SDK raises `ValueError`. Container crashes before `ResponsesHostServer` binds. Foundry runtime sees no agent. **The agent itself is fine — telemetry init is what killed it.** | Wrap telemetry init in `_init_telemetry()` (no-ops on missing env / SDK ImportError / any SDK exception). Never call `configure_azure_monitor()` raw at module/main scope. See `foundry-observability` gap row O-011 |
| **AppInsights connection PUT 400 ValidationError "AuthType for AppInsights Connection can only be ApiKey"** | Account-RP scope `2025-10-01-preview` in some regions rejects `authType: AAD` despite skill guidance (correlation IDs available) | Use `authType: ApiKey` with `credentials.key` in body. **BUT:** the key is silently dropped server-side — GET returns `credentials: null` and platform never injects the env var. There is no working workaround at the platform layer. File a support ticket; ship with guarded `_init_telemetry()` so the agent functions without telemetry; consider region pivot |
| **AppInsights connection account-level "1-per-category" limit** | Account-level `AppInsights` connections enforce a single-instance-per-category constraint — cannot create parallel connections in the same account. Re-creation requires DELETE first | DELETE the existing connection BEFORE re-PUT. Use `az rest --method DELETE` with full URI **as a variable** (do NOT inline `?api-version=...` — see next row) |
| **`az rest --method DELETE` strips `?api-version=...` query string when URI is inlined on PowerShell** | PowerShell argument parsing eats the `?api-version=` before `az` sees it. The DELETE then fails with "MissingApiVersionParameter" or behaves inconsistently against the bare resource without the version | Workaround: assign the URI to a variable first, then pass via `--uri $delUri`: `$delUri = "https://management.azure.com/.../connections/<name>?api-version=2025-10-01-preview"; az rest --method DELETE --uri $delUri` |
| ACA job uses old code after deploy | Postdeploy hook fails (`AZURE_AI_PROJECT_ENDPOINT not set`) | Run `cd infra/scripts && uv run deploy_job.py` manually after each `azd deploy` |
| Container starts but `agent_reference` errors in logs | `FoundryAgent` used for sub-agents | Replace with client-swap pattern |
| Protocol version error | Using `"v1"` | Use semver `"1.0.0"` |
| **Sticky `424 session_not_ready` for 8+ minutes; ZERO AppIn / LAW signal** | New Python module added to agent code but NOT included in Dockerfile `COPY` line. Module import fails on container start → `ResponsesHostServer` never binds → `/readiness` never returns 200 → Foundry retries readiness in long backoff → every Responses request returns sticky `424`. App Insights shows nothing because `_init_telemetry()` never runs (the module that calls it didn't even import). Near-impossible to diagnose from logs because there are no logs | Explicitly enumerate every Python module in the Dockerfile `COPY` line; do NOT rely on `COPY ./* .` or `COPY . .` globs (silently skip dotfiles + reorder hazards + cache-bust footguns). Pattern: `COPY container.py corpus.py my_kb_tool.py copilot-instructions.md ./`. After ANY new `.py` added to the agent module, re-check Dockerfile + rebuild |
| **`agent.yaml` `resources:` and `scale:` blocks silently dropped by `azd ai agent deploy`** | The deploy CLI accepts both blocks at the YAML schema layer but does NOT pass them through to the platform — deployed agents come up at `cpu=0.25 / memory=0.5Gi / no scale` regardless of what's in the YAML. Discovered May 2026; `PATCH versions/<n>` returns 405 (versions are immutable); `PUT versions/<n>` returns 405 (must auto-assign via POST) | **Workaround**: bypass `azd ai agent deploy` and POST directly to `<endpoint>/api/projects/<proj>/agents/<name>/versions?api-version=2025-11-15-preview` with the full `HostedAgentDefinition` body including `cpu`, `memory`, `min_replicas`, `max_replicas`, `image`, `env_vars`. Status transitions `creating` → `active` in <20s. File a CLI bug if not yet tracked upstream |
| **Scary RED `404 NotFound` block at the tail of `azd deploy <any-service>` (`agents/<key>/versions/<n>` not found); the actual deploy succeeded** | The `azure.ai.agents` azd extension's postdeploy hook fires after **every** `azd deploy` invocation (including unrelated services like `bot`, `workspace`, `mcp`) and looks up `agents/<service-key>/versions/<n>` — using the SERVICE KEY from `azure.yaml` verbatim, not the actual agent name. If your azure.yaml has e.g. `services.agent.host: azure.ai.agent` but the real agent is named `orchestrator`, the postdeploy hook 404s on `agents/agent/versions/<n>` every single time. Benign-but-loud false alarm; pollutes CI logs and CX in pilots | **Preferred**: rename the service key in `azure.yaml` to match the agent name (`services.orchestrator.host: azure.ai.agent`). **If you can't rename** (downstream scripts reference the key): error is cosmetic — verify with `azd ai agent show <agent-name>`. Track as `azure.ai.agents` extension bug; consider proposing an extension-level config like `agentName:` override |

### Container Logs (Logstream API)

```bash
# Get session ID from session_not_ready error, then:
curl -H "Authorization: Bearer $TOKEN" -H "Accept: text/event-stream" \
  "$PROJECT_ENDPOINT/agents/orchestrator/versions/$VER/sessions/$SID:logstream?api-version=2025-11-15-preview"
```

Returns SSE events with `{"stream":"stderr","message":"..."}` — shows startup logs, tracebacks.
Also: `azd ai agent monitor --session-id $SID`

### Useful Commands

```bash
azd ai agent show                    # Agent status, identities, version
azd ai agent monitor                 # Stream container logs
azd ai agent invoke "Hello!"         # Quick test
azd deploy <service> --no-prompt     # Redeploy without reprovisioning
```

---

## Migration from Initial Preview (pre-April 2026)

| Initial Preview | Refreshed Preview |
|----------------|-------------------|
| `from_agent_framework(agent).run()` | `ResponsesHostServer(agent).run()` |
| `ChatAgent` | `Agent` (from `agent_framework`) |
| `AzureOpenAIChatClient` | `FoundryChatClient` (from `agent_framework.foundry`) |
| `AzureAIClient(agent_name=...)` | Client-swap: `FoundryChatClient.client = project_client.get_openai_client(agent_name=...)` |
| `@ai_function` | `@tool(approval_mode="never_require")` |
| `azure-ai-agentserver-agentframework` | `agent-framework-foundry-hosting` |
| Protocol version `"v1"` | `"1.0.0"` (semver) |
| `extra_body={"agent_reference": ...}` | `get_openai_client(agent_name=...)` |
| Shared project MI | Dedicated agent Entra identity |
| Manual `start`/`stop` | Automatic compute lifecycle |
| `ENABLE_CAPABILITY_HOST=true` | `ENABLE_CAPABILITY_HOST=false` — NO CapabilityHost creation |
| `project_client.agents.list()` at startup | `TL_SUB_AGENTS` env var (avoids blocking readiness) |
| `azure.ai.projects` (sync) in container | `azure.ai.projects.aio` (ASYNC) — sync silently fails |

> **⚠️ `FoundryAgent` class (v1.1.1) is NOT compatible with refreshed preview.**
> It uses `extra_body={"agent_reference": ...}` internally — the old pattern that silently fails.
> Do NOT use `FoundryAgent` for sub-agent delegation. Use the client-swap pattern instead.

**Deadline:** Initial preview backend retires **May 22, 2026**.

Reference: [Migration guide](https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-hosted-agent-preview)

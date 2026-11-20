---
name: ghcp-hosted-agents
description: >
  Deploy Foundry hosted agents with the Microsoft Copilot SDK 2.0
  (microsoft-copilot-sdk, formerly GitHub Copilot SDK) using BYOK managed
  identity and the Invocations protocol. Covers client mode empty vs
  coding-agent, in-process runtime, host-owned tools with allow-lists,
  onPreToolUse governance hooks, session resume from a $HOME journal, and
  SDK 1.x migration. Use for streaming SSE output or long tool loops (>120s)
  that hit the Foundry gateway timeout with the Responses protocol.
  USE FOR: copilot sdk, microsoft copilot sdk, ghcp sdk, github copilot sdk
  migration, CopilotClient, mode empty, multi-tenant copilot agent,
  InvocationAgentServerHost, BYOK, bring your own key, invocations protocol,
  SSE streaming agent, long running agent, send_and_wait timeout,
  ghcp hosted agent, copilot client foundry.
  DO NOT USE FOR: MAF agents (use foundry-hosted-agents), prompt agents,
  declarative agents, general Azure deploy.
metadata:
  version: "4.0.0"
---

# Microsoft Copilot SDK 2.0 Hosted Agents on Foundry

Deploy Foundry hosted agents with the **Microsoft Copilot SDK 2.0**
(`microsoft-copilot-sdk`, renamed from `github-copilot-sdk`) and BYOK
(Bring Your Own Key) managed-identity authentication. No `GITHUB_TOKEN`
required. Uses the **Invocations protocol** (GA, version `2.0.0`) with SSE
streaming for unlimited tool-loop duration.

> **SDK 2.0 migration (v4.0.0).** The template now targets
> `microsoft-copilot-sdk~=2.0.1`: explicit `mode="empty"`, the native runtime
> loaded in-process, nested session options, named BYOK providers, host-owned
> tools behind an allow-list, an `onPreToolUse` deny hook, and per-turn session
> resume from a journal in `$HOME`. SDK 1.x code does not run unchanged — see
> § "Migrating from SDK 1.x". Live-validated on Foundry on 2026-11-20
> (tool call, resume recall, deny hook, cold-container resume).
>
> **RBAC (v2.0.9, still required).** Real model inference requires granting
> the hosted-agent **instance** identity the `Foundry User` role at BOTH the
> Foundry **account** and **project** scopes before invoking. See § "Identity
> & RBAC for hosted agents".

## When to Use the Copilot SDK Instead of MAF

**Shared deployment, distinct runtime.** Select/review the consumer against
the [hosted contract](../foundry-hosted-agents/references/hosted-contract.json).
The MAF private BASIC evidence does not certify this Copilot SDK/Invocations variant.
Keep its BYOK identities and permissions; do not copy the MAF implicit-access
assumption to a different account-level call.

The optional Python invoker now requires a durable `record` callback, or
`INVOCATION_EVIDENCE_FILE` for the CLI. Package the canonical
[operation evidence helper](../foundry-hosted-agents/references/python/operation_evidence.py)
beside it. It retains intent/HTTP metadata, rejects truncated or malformed SSE,
and treats the template runtime's `invocation_id` as a custom ID, not proof of
a retrievable Foundry response. Reconcile an uncertain effect; never repeat it
merely to recover output. See the [recovery contract](../foundry-hosted-agents/references/operation-recovery.md).

| Consideration | MAF | Copilot SDK 2.0 |
|---------------|-----|-----------------|
| **Auth** | `DefaultAzureCredential` → `FoundryChatClient` | BYOK: named provider + `bearer_token_provider` callback |
| **Protocol** | Responses API (request/response) | Invocations (SSE streaming) |
| **Tool loop limit** | ~120s (Foundry gateway timeout) | ♾️ (SSE keeps connection alive) |
| **Per-query overhead** | Low (1-3 internal turns) | Low in `mode="empty"`: 2 model calls for a one-tool query (measured, see § Performance) |
| **Skill discovery** | `SkillsProvider.from_paths()` (recommended) **OR** inline concat (legacy) | `skills.directories` / `skills.provider` session options |
| **Custom tools** | `@tool` decorator | `@define_tool` + `tools.available_tools` allow-list |
| **Governance hooks** | Middleware | `hooks.handlers.on_pre_tool_use` (allow / deny / ask) |
| **Toolbox** | `MCPStreamableHTTPTool` (was `client.get_toolbox()`, removed 1.3.0) | Remote MCP via `mcp.servers` |
| **Maturity** | Production-proven | Live-validated on Foundry (SDK 2.0.1) |

**Use the Copilot SDK when:**
- You need streaming progress events to the caller for workflows that run beyond the ~120s Responses gateway limit.
- You want the Copilot agent runtime (planning, skills, MCP, hooks, session journal) with your own Foundry model.
- Tool calls are slow (web scraping, Playwright, multi-site scans) and SSE keeps the connection alive.

**Use MAF when:**
- You need Foundry Toolbox built-ins (`web_search`, `code_interpreter`) or the Responses protocol (for example a Teams bot calling `responses.create()`).
- Your application already uses Microsoft Agent Framework. Its Copilot adapter does not support SDK 2.0 (see § "Migrating from SDK 1.x").

---

## Performance: SDK 2.0 in-process runtime

SDK 1.x spawned a Copilot CLI child process and, with default settings, each
query generated many internal tool calls; field measurements on 1.x showed
**~19s on MAF vs >220s** for a fast-MCP workload. SDK 2.0 loads a native
runtime in-process by default, and `mode="empty"` removes the ambient tools
and CLI defaults. The 1.x numbers no longer apply.

**Tested (2026-11-20, n=3 per row).** Foundry hosted agent, Sweden Central,
`gpt-5.4-mini` GlobalStandard, `microsoft-copilot-sdk` 2.0.1, `mode="empty"`,
one-tool query (`get_order`). `runtime start` and `session open` are measured
inside the container; the platform columns come from Foundry's
`X-Ms-Debug-Latency-*` response headers; wall time is the full
`azd ai agent invoke` call from a laptop, including CLI overhead.

| Runtime connection | Turn | Runtime start | Session open | Container readiness | Response begin | Wall (azd invoke) |
|--------------------|------|---------------|--------------|---------------------|----------------|-------------------|
| In-process (default) | Cold (new session) | 85–89 ms | 159–165 ms (create) | 2.56–2.64 s | 3.86–4.05 s | 10.5–11.6 s |
| In-process (default) | Warm (same session) | — | 23–25 ms (resume) | — | 0.16–0.31 s | 5.6–7.0 s |
| Spawned stdio (`COPILOT_SDK_DEFAULT_CONNECTION=stdio`) | Cold | 85–94 ms | 157–174 ms | 2.58–2.68 s | 3.87–4.29 s | 9.8–10.4 s |
| Spawned stdio | Warm | — | 22–26 ms | — | 0.14–0.16 s | 3.9–8.1 s |

The same session after `azd ai agent sessions stop` resumed in a new container
(runtime start 82 ms, session resume 158 ms) and recalled the earlier context.
A one-tool turn made **2 model calls** of ~2.7k input tokens each (1.9 s and
0.9 s model time). On Foundry, container readiness and model latency dominate;
the runtime transport does not.

**Documented** by the SDK team (not re-measured here): client + session + one
turn dropped from 5.25 s (TypeScript CLI) to 55.3 ms (Rust core in-process),
and memory for 10 clients from 1,383 MB to 126 MB
([announcement](https://commandline.microsoft.com/microsoft-copilot-sdk-2-0-github/)).
The `coding-agent` vs `empty` comparison was not re-measured on Foundry; the
issue reporter measured ~2.9k vs ~2.7k first-turn input tokens locally.

| | In-process (default) | Spawned stdio |
|---|---|---|
| Select | `RuntimeConnection.for_inprocess()` or `for_default()` | `RuntimeConnection.for_spawned_stdio()` or `COPILOT_SDK_DEFAULT_CONNECTION=stdio` with `for_default()` |
| Crash isolation | **None** — a native runtime crash terminates the agent process | Runtime runs in a child process |
| Process env / working directory per client | Not supported | Supported on the connection |
| Native assets | Must match OS, CPU and C library (glibc vs musl) | Same staged runtime |
| Measured on Foundry | See table | See table |

Source: [In-process runtime](https://github.com/microsoft/copilot-sdk/blob/main/docs/setup/in-process-runtime.md),
[v2 breaking changes](https://github.com/microsoft/copilot-sdk/blob/main/docs/v2-breaking-changes.md#in-process-runtime-hosting-by-default).

---

## Runtime Pattern (Copilot SDK 2.0 + Invocations)

> **MUST:** Copy verbatim from [`references/container.py`](references/container.py),
> then replace the sample tools (`get_order`, `issue_refund`) with your own and
> keep `available_tools` and `DENIED_TOOLS` in step with them.

The template provides:
1. `_ensure_client()` — `CopilotClient(mode="empty", runtime=RuntimeConnection.for_default(base_directory=$HOME/.copilot-sdk), github={"use_logged_in_user": False})`
2. `_session_options()` — the options re-supplied on **every** create and resume: model, named BYOK provider, permissions, hooks, streaming, tools and allow-list
3. `_open_session()` — creates the SDK session keyed by `FOUNDRY_AGENT_SESSION_ID` on the first turn, resumes it from the journal afterwards
4. `_stream_response()` — emits one `host.session` frame (`created`/`resumed` + timings), streams session events as SSE, then disconnects the session
5. `handle_invoke()` — `@app.invoke_handler` returning `StreamingResponse`

```
container.py → CopilotClient(mode="empty") + InvocationAgentServerHost → port 8088
  ├── in-process native runtime, home = $HOME/.copilot-sdk (persisted per Foundry session)
  ├── BYOK: inference.providers[foundry] + bearer_token_provider (ai.azure.com scope)
  ├── tools: define_tool + available_tools ["custom:get_order", "custom:issue_refund"]
  ├── hooks: on_pre_tool_use denies issue_refund
  └── SSE streaming (no timeout on long tool loops)
```

**Key points:**
- `FOUNDRY_PROJECT_ENDPOINT` is **injected by the platform** — never declare it
  under the `azure.yaml` agent service's `environmentVariables` list (see
  § "azure.yaml (unified GA deployment)"). The template derives the account
  URL from it and calls `<account>/openai/v1/`.
- BYOK scope is `https://ai.azure.com/.default` — NOT `cognitiveservices.azure.com`.
- The token callback runs before each model request, so long sessions no longer
  need a fresh session per hour.
- Foundry persists `$HOME` per hosted session across turns and idle periods
  ([Manage hosted agent sessions](https://learn.microsoft.com/azure/foundry/agents/how-to/manage-hosted-sessions)),
  so the SDK journal under `$HOME/.copilot-sdk/session-state/<id>` survives
  container restarts.
- `system_message` requires dict format: `{"mode": "replace", "content": "..."}`
  (loaded from `copilot-instructions.md` when present).
- `PermissionHandler.approve_all` approves permission requests for unattended
  agents; the `on_pre_tool_use` hook still runs first and can deny.
- Optional remote MCP: set `MCP_SERVER_FQDN`; the template adds
  `mcp.servers` and the `mcp:*` allow-list entry (documented, not exercised by
  the CI fixture).

---

## Why Invocations Protocol (Not Responses)

The Copilot SDK could also run behind `ResponsesHostServer` using MAF's `GitHubCopilotAgent` adapter (SDK 1.x only — the adapter is not compatible with SDK 2.0):

```python
# ⚠️ This pattern DOES NOT WORK for long tool loops on Foundry
from agent_framework_foundry_hosting import ResponsesHostServer
from agent_framework.github import GitHubCopilotAgent

agent = GitHubCopilotAgent(...)
server = ResponsesHostServer(agent)
server.run()
```

**Why it fails:** `GitHubCopilotAgent.send_and_wait()` blocks until the full response
completes. Default timeout is 60s (configurable). But **Foundry's gateway has a ~120s
hard timeout** on non-streaming responses. Any tool-heavy workflow (web scraping,
multi-site scanning) taking >120s returns a gateway timeout.

**Invocations protocol solves this:** SSE events stream continuously, keeping the
connection alive. A query using 50+ tool calls over 5 minutes works perfectly because
events flow throughout.

| Approach | Max Duration | Why |
|----------|-------------|-----|
| ResponsesHostServer + send_and_wait | ~120s | Foundry gateway timeout on non-streaming |
| InvocationAgentServerHost + SSE | Unlimited | Events stream continuously |

**Critical:** the `azure.yaml` agent service must declare `protocol: invocations`
only — do **not** add a `responses` protocol entry. `InvocationAgentServerHost`
only serves `/invocations`; the `/responses` path returns 404 even if declared.
See the troubleshooting row **"responses protocol not declared" (bot 400)** —
dual protocols don't work. **WHY:** `InvocationAgentServerHost` is the only
server type the Copilot SDK hosted template uses; serving Responses requires
switching to the MAF runtime (`ResponsesHostServer`) entirely. External
callers (bot, eval scripts) must POST to the Invocations SSE endpoint
directly, or use `azd ai agent invoke --protocol invocations`. If you need
`oai.responses.create()` for a Teams bot, use MAF runtime instead.

---

## pyproject.toml

**Copy** `references/pyproject.toml` into your project root and update `name` and `version`.

**Notes:**
- `microsoft-copilot-sdk~=2.0.1` provides `CopilotClient`, `RuntimeConnection`, `define_tool`, session options and event types. **Uninstall `github-copilot-sdk` first** (`pip uninstall github-copilot-sdk`): both distributions install the same `copilot` import package ([identities](https://github.com/microsoft/copilot-sdk/blob/main/docs/v2-breaking-changes.md#microsoft-copilot-sdk-identities))
- `azure-ai-agentserver-invocations~=1.3.0` provides `InvocationAgentServerHost`; it requires `azure-ai-agentserver-core>=2.3.0,<3.0.0`, capped here with `~=2.3.0`
- `azure-identity~=1.27.0` supplies the async `DefaultAzureCredential` used by the token callback
- `pydantic` backs the `@define_tool` parameter models

---

## Dockerfile

**Copy** `references/Dockerfile` into your project root. It stages the SDK's
native runtime at build time:

```dockerfile
ENV COPILOT_CLI_EXTRACT_DIR=/opt/copilot-runtime
RUN python -m copilot download-runtime --in-process && chmod -R a+rX /opt/copilot-runtime
ENV COPILOT_SKIP_CLI_DOWNLOAD=1
```

**Why:** SDK 2.0 Python wheels do not bundle the native runtime; without
pre-staging, the SDK downloads it from GitHub Releases on first use into
`~/.cache/copilot-sdk/...`
([Python README § Runtime](https://github.com/microsoft/copilot-sdk/blob/main/python/README.md#runtime)).
Foundry hosted agents run with `HOME=/home/session`, so a runtime downloaded at
build time into `/root/.cache` is not found at run time. A fixed
`COPILOT_CLI_EXTRACT_DIR` makes the build-time and run-time paths identical, and
`COPILOT_SKIP_CLI_DOWNLOAD=1` turns a missing runtime into a startup error
instead of a silent download.

- Without pre-staging, the container needs egress to GitHub Releases on its first request.
- Alpine/musl base images need the musl native assets; the reference uses `python:3.12-slim` (glibc).
- `azure.yaml` sets `docker.remoteBuild: true` so `azd deploy` builds on ACR, not on a local Docker daemon.

---

## BYOK Authentication Deep Dive

BYOK lets the Copilot runtime call your Foundry model deployment instead of
GitHub-hosted models. No `GITHUB_TOKEN` needed.

### How It Works

```
create_session / resume_session(inference={providers, models}, github={"capi": {"enabled": False}})
  └── runtime calls bearer_token_provider before each model request
      └── DefaultAzureCredential → token for https://ai.azure.com/.default
          └── POST https://<account>.services.ai.azure.com/openai/v1/responses
```

### Provider configuration (SDK 2.0)

The singular `provider` option and `ProviderConfig` are gone. Register a
**named connection** (`NamedProviderConfig`) and a **model definition** under
`inference`, then select the model as `provider/id`
([named providers](https://github.com/microsoft/copilot-sdk/blob/main/docs/v2-breaking-changes.md#named-provider-connections-and-model-definitions),
[managed identity BYOK](https://github.com/microsoft/copilot-sdk/blob/main/docs/setup/azure-managed-identity.md)):

```python
from azure.identity.aio import DefaultAzureCredential
from copilot.session import NamedProviderConfig

credential = DefaultAzureCredential()

async def get_token(_args) -> str:          # raw token, no "Bearer " prefix
    return (await credential.get_token("https://ai.azure.com/.default")).token

session_opts = dict(
    model="foundry/chat",                   # canonical provider/id
    github={"capi": {"enabled": False}},    # BYOK-only catalog
    inference={
        "providers": [NamedProviderConfig(
            name="foundry", type="openai", wire_api="responses",
            base_url=f"{ACCOUNT_URL}/openai/v1/",   # https://<account>.services.ai.azure.com
            bearer_token_provider=get_token,
        )],
        "models": [{"provider": "foundry", "id": "chat",
                    "model_id": DEPLOYMENT, "wire_model": DEPLOYMENT}],
    },
)
```

| Field | Meaning |
|-------|---------|
| Connection `name` | Stable connection id (no `/`); model definitions reference it as `provider` |
| Model `id` | Provider-local id; select it as `foundry/chat` |
| `model_id` | Base model used for capability lookup (defaults to `id`) |
| `wire_model` | Deployment name sent to Foundry (defaults to `id`) |
| `bearer_token_provider` | Called before each request; takes precedence over `bearer_token`/`api_key`; never persisted |

`github.capi.enabled: False` keeps the catalog BYOK-only. Adding a provider no
longer disables CAPI implicitly. An alternative to model definitions is
`inference.default_provider="foundry"` with an unqualified `model` (pass-through).

### Common BYOK Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Wrong scope | 401 Unauthorized | Use `ai.azure.com`, not `cognitiveservices.azure.com` |
| Legacy `provider=` keyword (1.x) | Python: `TypeError: ... unexpected keyword argument 'provider'` | Move to `inference.providers` + `inference.models` |
| Resume without re-supplying `inference` | `Previously registered provider model 'foundry/chat' is no longer registered` (reported) | Pass the same providers and models on every resume — credentials and callbacks are never persisted |
| `github.capi` left enabled with a BYOK-only deployment | Model resolves against the Copilot catalog | Set `github={"capi": {"enabled": False}}` |
| Permission error during deploy or invoke | 403 / `PermissionDenied` | Hard FAIL except the exact immediate-post-active readiness envelope documented under § "Invoking the Agent". That narrow case retries the same path; all others require root-cause investigation. The two required instance grants (account + project) are a documented prerequisite, not an invoke-time workaround - do not add further grants to route around a failure |

---

## Session options (SDK 2.0)

```python
client = CopilotClient(
    mode="empty",                                   # mandatory: "empty" or "coding-agent"
    runtime=RuntimeConnection.for_default(base_directory=STATE_DIR),
    github={"use_logged_in_user": False},           # BYOK host: no GitHub sign-in
)
await client.start()

session = await client.create_session(              # resume_session(sid, **same options)
    session_id=sid,
    model="foundry/chat",
    working_directory=str(Path.home()),
    system_message={"mode": "replace", "content": "You are a helpful assistant."},
    github={"capi": {"enabled": False}},
    inference={"providers": [...], "models": [...]},
    permissions={"on_request": PermissionHandler.approve_all},
    hooks={"handlers": {"on_pre_tool_use": on_pre_tool_use}},
    events={"streaming": True},
    tools={"definitions": [get_order], "available_tools": ["custom:get_order"]},
    skills={"directories": ["/app/skills"]},        # optional
    mcp={"servers": {"remote": {"type": "http", "url": "https://<fqdn>/mcp", "tools": ["*"]}}},  # optional
)
```

Option mapping from 1.x (Python names;
[full table](https://github.com/microsoft/copilot-sdk/blob/main/docs/v2-breaking-changes.md#restructured-session-options)):

| SDK 1.x | SDK 2.0 |
|---------|---------|
| `provider=ProviderConfig(...)` | `inference={"providers": [NamedProviderConfig(...)], "models": [...]}` |
| `on_permission_request=` | `permissions={"on_request": ...}` |
| `streaming=True` | `events={"streaming": True}` |
| `tools=[...]`, `available_tools=[...]` | `tools={"definitions": [...], "available_tools": [...]}` |
| `skill_directories=[...]` | `skills={"directories": [...]}` |
| `mcp_servers=...` | `mcp={"servers": {name: config}}` (dict keyed by server name) |
| `hooks=...` | `hooks={"handlers": {...}}` |
| `github_token=` on the client | `github={"token": ...}` on the client or per session |
| `CopilotClient()` | `CopilotClient(mode="coding-agent" \| "empty")` |

Imports: `from copilot import CopilotClient, RuntimeConnection, define_tool`,
`from copilot.session import NamedProviderConfig, PermissionHandler`,
`from copilot.session_events import SessionEventType`. `copilot.generated` is
now private (`copilot._generated`); use the public modules.

---

## Choosing mode and multi-tenant patterns

Source: [Multi-tenancy and server deployments](https://github.com/microsoft/copilot-sdk/blob/main/docs/setup/multi-tenancy.md).

| | `mode="empty"` (template) | `mode="coding-agent"` |
|---|---|---|
| Ambient tools | None — each session opts in via `tools.available_tools` | CLI-like coding tools, including host filesystem access |
| Persistence | Client must set `base_directory` or `session_fs` | Defaults to `~/.copilot` |
| Intended for | Services, shared or multi-user hosts | Single-user coding assistants |

**Patterns proven in the template (live, 2026-11-20):**

1. **Explicit storage.** `CopilotClient(mode="empty")` raises
   `ValueError ... requires base_directory, session_fs, or a TcpRuntimeConnection`
   without one. The template uses `$HOME/.copilot-sdk`; Foundry already isolates
   `$HOME` per hosted session. On a shared host, give each tenant its own
   `base_directory` or route storage through `session_fs`.
2. **Allow-list every session.** In empty mode, `create_session` and
   `resume_session` raise `ValueError` without `tools.available_tools`.
   Name tools by source: `custom:<tool>`, `mcp:<server>-<tool>` (or `mcp:*`),
   `builtin:<tool>`. Avoid `builtin:*` on shared hosts.
3. **Map the Foundry session to the SDK session.** Use
   `FOUNDRY_AGENT_SESSION_ID` as the SDK `session_id`; the journal lives in
   `base_directory/session-state/<id>/`. The template resumes when that
   directory exists and creates the session otherwise.
4. **Re-supply on every resume.** Providers and token callbacks, tool
   definitions, hooks and permission handlers are never persisted. Pass the
   same option set to `resume_session` — the template builds it in one
   function and disconnects after each turn, so every later turn is a genuine
   resume (also after a container restart).
5. **`onPreToolUse` as a governance gate.** Return
   `{"permissionDecision": "deny", "permissionDecisionReason": "..."}`; the
   handler never runs and the stream shows `tool.execution_complete` with
   `success: false` and `error.code: "denied"`. The model then explains the
   refusal. Live output:
   `Denied by preToolUse hook: issue_refund requires human approval and is blocked for this agent`.
6. **Per-session GitHub identity** (only when CAPI models or GitHub tools are
   used): pass `github={"token": ...}` or `github={"token_provider": ...}` on
   `create_session`/`resume_session` instead of sharing one client token.

---

## Migrating from SDK 1.x

1. `pip uninstall github-copilot-sdk && pip install "microsoft-copilot-sdk~=2.0.1"`.
2. Add `mode=` to `CopilotClient`. Choose `"empty"` for hosted agents.
3. Replace `provider=ProviderConfig(...)` with named `inference.providers` +
   `inference.models`, and select `provider/id`. In Python the old keyword
   raises `TypeError`; the issue reporter observed TypeScript silently
   ignoring it, after which the first send failed with
   `Model "gpt-5.4-mini" is not available`.
4. Nest the remaining options (table in § "Session options (SDK 2.0)").
5. Stage the native runtime in the Dockerfile (§ "Dockerfile").
6. Re-supply providers, tools and hooks on every resume.

**Staying on 1.x.** Microsoft Agent Framework's Copilot adapters
(`agent-framework-github-copilot`, .NET `Microsoft.Agents.AI.GitHub.Copilot`)
depend on the 1.x SDK and are not compatible with 2.0; do not install them
alongside `microsoft-copilot-sdk`
([MAF integration](https://github.com/microsoft/copilot-sdk/blob/main/docs/integrations/microsoft-agent-framework.md),
[PyPI](https://pypi.org/project/agent-framework-github-copilot/)). Such apps
should pin `github-copilot-sdk~=1.0` and use skill version 3.0.0 of this
guide until compatible adapters ship.

---

## Session Event Types

| Event Type | Meaning | Action |
|------------|---------|--------|
| `host.session` | Emitted by the template, not the SDK: `state` (`created`/`resumed`), runtime start and session-open timings | Evidence of resume |
| `SESSION_IDLE` | Response complete | Stop streaming, yield `done` event |
| `SESSION_ERROR` | Agent error | Yield error event, stop |
| `assistant.message` | Final assistant response | Contains full response text |
| `assistant.message_delta` | Streaming content chunk | Accumulate for progressive display |
| `assistant.streaming_delta` | Raw streaming delta | Lower-level than message_delta |
| `tool.execution_start` | Tool call started (`toolName`, `arguments`) | Log for debugging |
| `tool.execution_complete` | Tool call finished; `success: false` + `error.code: "denied"` when a hook denied it | Audit |
| `hook.start` / `hook.end` | Hook invocation (`hookType`, e.g. `preToolUse`) | Audit |
| `assistant.usage` | Per-model-call tokens and duration | Cost / latency tracking |
| `assistant.turn_start` / `assistant.turn_end` | Turn boundaries | Track turn count |

---

## Invoking the Agent

**Primary path — `azd ai agent invoke`.** Per the current GA CLI (verified
against a locally installed `azure.ai.agents` `1.0.0-beta.4` extension),
`azd ai agent invoke` DOES wrap the positional message argument correctly
and accepts a raw JSON payload for the Invocations protocol:

```bash
azd ai agent invoke "<agent-name>" '{"input": "Say hello in one short sentence."}' \
  --protocol invocations \
  --output raw \
  --timeout 180
```

- `--protocol invocations` selects the Invocations protocol (the CLI
  defaults to `responses` otherwise)
- `--output raw` (or `-o raw`) dumps the unmodified server response
  (status line, headers, body) — the SSE `data:` lines are visible verbatim,
  which is what you want to grep for `assistant.message` /
  `assistant.message_delta`
- `--timeout <seconds>` (or `-t`) bounds the request; the CLI default is
  1800s, which is far longer than most smoke/CI budgets need

Immediately after a new version becomes `active`, the first model call can
briefly return an HTTP-200 SSE readiness envelope while the platform's
implicit agent permission finishes propagating. The exception is exact and
has these guards:

1. The first recognized auth failure must be a `model.call_failure` event
   with `statusCode: 401` whose
   `PermissionDenied` error contains both
   `Microsoft.CognitiveServices/accounts/OpenAI/responses/write` and
   `POST /openai/v1/responses`.
2. After that anchor, subsequent generic 401 `PermissionDenied`
   `model.call_failure` events and `session.info` events containing
   `transient_auth_error` may interleave. At least one transient-info event
   is required. The anchor must not repeat; a repeated anchored failure is
   outside the observed readiness envelope and remains a hard failure.
3. The envelope must end with a terminal error containing
   `Authentication failed with provider` and
   `HTTP 401`.

Observed streams may include benign `session.usage_info` and
`assistant.turn_end` lifecycle events inside the recognized envelope. The SSE
epilogue is a separate `event: done` frame whose JSON payload contains a
non-empty string `invocation_id`; accept it only after assistant success or
the recognized provider-auth terminal. Untyped data outside that done frame,
unknown typed events inside the envelope, or a malformed done payload remain
hard failures.

If assistant output arrives after the recognized provider-auth terminal, it
establishes recovered assistant output. Only after that recovery may
`session.usage_info` and `assistant.turn_end` follow before the exact done
frame. Those lifecycle events before assistant recovery do not convert the
terminal failure into success.

Only that complete immediate-post-active sequence is retryable. Retry the
**same JSON positional invoke path** with bounded backoff (six attempts,
15 seconds between attempts). Do not switch invocation methods and do not
add a role grant. Missing, malformed, reordered, or unrelated terminal
events remain a hard failure.

> The older claim that `azd ai agent invoke` "does not wrap user input" was
> a pre-GA defect specific to earlier preview builds. It does not reproduce
> against the current GA CLI and is retired from this skill — do not carry
> it forward into new guidance.

### Via curl or the reference script (advanced/optional)

For callers that need to parse the raw SSE stream directly (e.g. wiring a
bot integration rather than a one-off smoke test), use
`references/invoke_agent.py` as a library or standalone script:

```bash
export AZURE_AI_PROJECT_ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
export AGENT_NAME="my-agent"
python references/invoke_agent.py "What is the capital of France?"
```

The `invoke_invocations()` function POSTs to
`{endpoint}/agents/{agent_name}/endpoint/protocols/invocations?api-version=v1`
(GA endpoint API version literal `v1` — no `Foundry-Features` preview
header) and parses both `assistant.message` and `assistant.message_delta`
events, preferring the complete message when available.

**Important:** Always parse both event types. Some responses only emit deltas
without a final complete message event.

---

## Evaluation

### Two-Phase Eval (Invocations Protocol)

Foundry eval SDK's `azure_ai_agent` target does not route to hosted agent endpoints.
Use a two-phase workaround:

1. **Invoke**: Call the agent via Invocations endpoint, collect responses
2. **Score**: Submit query+response pairs to Foundry evaluators

### Eval Data Format for Task Adherence

Task Adherence evaluates whether the agent followed its system instructions.
Include the system message in conversation array format:

```python
eval_item = {
    "query": [
        {"role": "system", "content": "Your system prompt here..."},
        {"role": "user", "content": [{"type": "text", "text": "User question"}]},
    ],
    "response": [
        {"role": "assistant", "content": [{"type": "text", "text": "Agent response"}]},
    ],
}
```

### Eval Judge Model Sensitivity

| Judge Model | Task Adherence | Other Evaluators |
|-------------|---------------|------------------|
| `gpt-5.4` | **7%** (overly strict) | Stable |
| `gpt-5.4-mini` | **86%** (accurate) | Stable |

**Always use `gpt-5.4-mini`** as the judge model for Task Adherence.
`gpt-5.4` penalizes responses for claiming tool usage that can't be verified
from response-only data. All other evaluators (Coherence, Intent Resolution,
Task Completion) are stable across both judge models.

### Validated Scores (14-query benchmark)

| Evaluator | Score | Notes |
|-----------|-------|-------|
| **Coherence** | 100% | Identical to MAF |
| **Intent Resolution** | 100% | Identical to MAF |
| **Task Adherence** | 86% | Identical to MAF (gpt-5.4-mini judge) |
| **Task Completion** | 64% | Identical to MAF |
| **Tool Usage (URLs)** | 100% | All responses contain source URLs |

---

## azure.yaml (unified GA deployment)

The old **two-file** contract (`agent.yaml` + a separately hand-wired
`azure.yaml`) is gone. A single `azure.yaml` at the project root is now the
source of truth for both the Foundry project/model deployment and the
hosted agent itself — declared as a graph of `services`, each with a `host`
field and a `uses` list of dependencies. This is the same unified shape
`foundry-hosted-agents` uses, adapted for the Copilot SDK's Invocations
protocol instead of MAF's Responses protocol.

> **MUST:** Copy verbatim from [`references/yaml/azure.yaml`](references/yaml/azure.yaml). Do NOT redefine inline — the validator enforces single-source-of-truth. That file is the canonical `azure.ai.project` + `azure.ai.agent` service pair for a container-built Copilot SDK hosted agent connecting to a **pre-provisioned** Foundry project.

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/Azure/azure-dev/main/schemas/v1.0/azure.yaml.json
name: my-agent-project

requiredVersions:
  extensions:
    azure.ai.agents: '>=1.0.0-beta.4'

services:
  ai-project:
    host: azure.ai.project
    # Point at an EXISTING project instead of provisioning a new one.
    endpoint: ${FOUNDRY_PROJECT_ENDPOINT}

  my-agent:
    host: azure.ai.agent
    project: .
    language: docker
    docker:
      remoteBuild: true
    uses:
      - ai-project
    kind: hosted
    name: my-agent
    protocols:
      - protocol: invocations
        version: 2.0.0
    environmentVariables:
      - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
        value: ${AZURE_AI_MODEL_DEPLOYMENT_NAME}
    container:
      resources:
        cpu: "1"
        memory: 2Gi

infra:
  provider: microsoft.foundry
```

### Critical rules

| Rule | Why |
|------|-----|
| `docker.remoteBuild: true` | Builds the image on ACR. Without it, azd 1.37.3 + `azure.ai.agents` 1.2.0 built locally when a Docker daemon was available (observed 2026-11-20) |
| `kind: hosted` on the `azure.ai.agent` service | Marks it as a containerized/source-built hosted agent (as opposed to a Foundry Agent Service prompt agent) |
| Protocol `invocations`, version `2.0.0` | Current GA protocol + version for the Copilot SDK template's `InvocationAgentServerHost`. Do NOT add a `responses` protocol entry — see § "Why Invocations Protocol (Not Responses)" |
| `container.resources` nested object | NOT a top-level `resources:` list |
| NO `FOUNDRY_PROJECT_ENDPOINT` in `environmentVariables` | Reserved — the platform injects it automatically, along with `FOUNDRY_PROJECT_ARM_ID`, `FOUNDRY_AGENT_NAME`, `FOUNDRY_AGENT_VERSION`, `FOUNDRY_AGENT_SESSION_ID`, and `APPLICATIONINSIGHTS_CONNECTION_STRING`. Declaring any of them yourself is redundant at best and risks shadowing the platform value |
| `uses: [ai-project]` on the agent service | Forms the dependency graph `azd` resolves at provision/deploy time — the agent can't reference the project's model deployment without it |
| Connect to an existing project via `endpoint:` | Set `services.ai-project.endpoint` from `${FOUNDRY_PROJECT_ENDPOINT}` to reuse a pre-provisioned Foundry project instead of having `azd` provision a new one |
| `infra.provider: microsoft.foundry` | Selects the Foundry extension's bicep-less provisioning provider for the unified services graph |

### Guided init vs. direct-copy brownfield deploy

The **recommended guided path** adopts the manifest and wires the existing
project/registry context into the active azd environment:

```bash
PROJECT_ID="/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>"
azd ai agent init -m ./azure.yaml \
  --project-id "$PROJECT_ID" \
  --deploy-mode container
```

If you instead copy the canonical files into an existing repository and run
`azd deploy` directly (**direct-copy**), `azure.yaml` alone is insufficient.
The `azure.ai.agents` service target requires the full project ARM ID,
project endpoint, subscription, and bare ACR login server in the **active
azd environment**:

```bash
azd env set AZURE_SUBSCRIPTION_ID "<sub-id>"
azd env set FOUNDRY_PROJECT_ENDPOINT \
  "https://<account>.services.ai.azure.com/api/projects/<project>"
azd env set AZURE_AI_PROJECT_ID \
  "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>"
azd env set AZURE_CONTAINER_REGISTRY_ENDPOINT "<registry>.azurecr.io"
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "<model-deployment>"
azd deploy my-agent --no-prompt
```

`AZURE_CONTAINER_REGISTRY_ENDPOINT` is a **bare hostname** — no
`https://` scheme and no trailing slash. This direct-copy limitation is
the adoption wiring covered by
[Azure/azure-dev #8981](https://github.com/Azure/azure-dev/pull/8981):
`azd ai agent init ... --deploy-mode container` wires it automatically;
plain `azd deploy` cannot infer the omitted brownfield values.

### Installing the `azd` Foundry extensions

```bash
azd ext install microsoft.foundry
```

`microsoft.foundry` is a **beta meta-package** — it contributes no
commands of its own. Installing it pulls in every individual Foundry
extension: `azure.ai.agents` (`azd ai agent`, the one this skill uses),
`azure.ai.connections`, `azure.ai.inspector`, `azure.ai.projects`,
`azure.ai.routines`, `azure.ai.skills`, and `azure.ai.toolboxes`. It is
**not** a rename or replacement of `azure.ai.agents` — the agent
extension still owns the `azd ai agent` command group, the
`azure.ai.agent` service `host` value, and the `microsoft.foundry`
**provisioning** identifier azd uses internally when it synthesizes
infrastructure. Installing just `azure.ai.agents` also pulls in
`azure.ai.inspector` (a dependency), so it's a valid narrower
alternative to the meta-package:

```bash
# Just the agent surface (also pulls in azure.ai.inspector)
azd ext install azure.ai.agents

# Upgrade later
azd ext upgrade microsoft.foundry
```

Verify what's installed:

```bash
azd ext list --output json
```

---

## `azd env` variables for the `azure.ai.agents` extension

The guided `azd ai agent init` path is **bicep-less by default** — it
doesn't write an `infra/` directory; `azd` synthesizes infrastructure from
the `services` graph in `azure.yaml`. Guided init writes the brownfield
values below automatically. A direct-copy deploy must set them explicitly
before `azd deploy`:

| Env var | Set via | Format | Why it matters |
|---------|---------|--------|-----------------|
| `AZURE_SUBSCRIPTION_ID` | `azd env set` or guided init | subscription GUID | Selects the subscription containing the existing project and registry |
| `FOUNDRY_PROJECT_ENDPOINT` | `azd env set` or guided init | `https://<account>.services.ai.azure.com/api/projects/<project>` | Deploy-time project lookup for direct-copy brownfield deploy; also injected by Foundry into the running container, but MUST NOT be listed under `environmentVariables` |
| `AZURE_AI_PROJECT_ID` | `azd env set` or guided init | `/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>` | Full ARM ID required by the Foundry project resolver; an endpoint alone is insufficient |
| `AZURE_CONTAINER_REGISTRY_ENDPOINT` | `azd env set` or guided init | `<registry>.azurecr.io` | Bare ACR login server used for container build/push; no scheme or trailing slash |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | `azd ai agent init` records it automatically from the deployment you select; change later with `azd env set` | deployment name (e.g. `gpt-5.4-mini`) | Projected through the agent service's `environmentVariables` entry in `azure.yaml`, and read by `container.py` as `os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]` |

> **Deploy-time azd env vs. runtime container env.**
> `FOUNDRY_PROJECT_ENDPOINT` MUST be set in the active azd environment for
> direct-copy brownfield deploy, but MUST NOT be projected through the
> agent's `environmentVariables` list. Foundry injects it into the running
> container. The same container-only prohibition applies to
> `FOUNDRY_PROJECT_ARM_ID`, `FOUNDRY_AGENT_NAME`,
> `FOUNDRY_AGENT_VERSION`, `FOUNDRY_AGENT_SESSION_ID`, and
> `APPLICATIONINSIGHTS_CONNECTION_STRING`.

---

## Identity & RBAC for hosted agents

`azd ai agent` creates two distinct managed identities you must not
confuse:

- **Blueprint identity** — a stable Entra identity bound to the agent
  definition (visible via `azd ai agent show`). It handles deploy-time
  wiring (ACR pulls, version registration). **The blueprint identity
  needs no data-plane role grants for inference.**
- **Instance identity** — a per-version (per-instance) service principal
  created for the active agent *version*. **This** identity is what the
  running agent presents when it calls the model through the project
  endpoint. It is the identity that must hold model-inference permission.

The blueprint identity needs no role assignments; only the instance identity does.

### Required: grant the instance identity `Foundry User` at BOTH scopes

Real model inference through a hosted agent requires the **instance**
identity to hold the **`Foundry User`** role
(GUID `53ca6127-db72-4b80-b1b0-d745d6d5456d`) at **both** of these scopes
**before** the first invocation:

| Role | Assignee | Scope | Why |
|------|----------|-------|-----|
| `Foundry User` (`53ca6127-db72-4b80-b1b0-d745d6d5456d`) | Instance identity | Foundry **account** | Model gateway authorizes `responses/write` at account scope |
| `Foundry User` (`53ca6127-db72-4b80-b1b0-d745d6d5456d`) | Instance identity | Foundry **project** | Data-plane project authorization for the agent's calls |

Controlled Azure testing proved this is the **minimum** working contract:
project-scope-only failed with 401, account-scope-only failed with 401,
and **both scopes together succeeded**. Grant one without the other and
real inference returns `PermissionDenied` /
`Microsoft.CognitiveServices/accounts/OpenAI/responses/write`.

> **Why the earlier "no grant" contract was wrong.** A prior build of
> this skill claimed the Foundry service granted the agent identity its
> permissions internally with no client-side assignment. That was
> validated only against an upstream **echo** agent that never called a
> real model, so the missing inference permission never surfaced. On a
> live model deployment it 401s deterministically. This is a persistent
> **authorization** gap, not a transient — do not paper over it in a
> retry classifier.

### Scope construction (no hardcoded IDs)

`AZURE_AI_PROJECT_ID` is the **full project ARM resource ID**:

```
/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>
```

Derive both scopes from it with pure string manipulation:

```bash
project_scope="$AZURE_AI_PROJECT_ID"                 # full project ARM id
account_scope="${AZURE_AI_PROJECT_ID%/projects/*}"   # strip /projects/<name>
```

Grant the instance identity at both scopes, **capturing each assignment's
ARM id** so teardown can revoke exactly what it created (never a standing
grant):

```bash
account_assignment_id=$(az role assignment create \
  --role 53ca6127-db72-4b80-b1b0-d745d6d5456d \
  --assignee-object-id "$instance_principal_id" \
  --assignee-principal-type ServicePrincipal \
  --scope "$account_scope" \
  --query id -o tsv)
project_assignment_id=$(az role assignment create \
  --role 53ca6127-db72-4b80-b1b0-d745d6d5456d \
  --assignee-object-id "$instance_principal_id" \
  --assignee-principal-type ServicePrincipal \
  --scope "$project_scope" \
  --query id -o tsv)
```

If a grant may already exist, resolve its id idempotently first and only
create (and only later revoke) the ones you actually add:

```bash
account_assignment_id=$(az role assignment list \
  --assignee "$instance_principal_id" \
  --role 53ca6127-db72-4b80-b1b0-d745d6d5456d \
  --scope "$account_scope" --query "[0].id" -o tsv)
# empty -> create it (owned by you); non-empty -> pre-existing, do not revoke
```

### Discovering the instance identity (deterministic)

`azd ai agent show --output json` exposes **both** managed identities by
explicit field path — do not scan the object heuristically:

```bash
azd ai agent show --output json
# .instance_identity.principal_id  -> the runtime per-version INSTANCE MI (grant this)
# .blueprint.principal_id          -> the blueprint identity (never grant)
# fallbacks: .versions.latest.instance_identity.principal_id
#            .versions.latest.blueprint.principal_id
INSTANCE_PID=$(azd ai agent show --output json | jq -er '.instance_identity.principal_id')
BLUEPRINT_PID=$(azd ai agent show --output json | jq -er '.blueprint.principal_id')
```

Discover and log **both** so the instance-vs-blueprint distinction is explicit,
then grant **only** `$INSTANCE_PID`. The instance identity is populated shortly
after the version goes active; if it is briefly empty, retry `azd ai agent show`
up to twice with a short wait. `$instance_principal_id` above is this
`instance_identity.principal_id` — never the `blueprint.principal_id`.

> **Least-privilege note.** The grantor needs
> `Microsoft.Authorization/roleAssignments/write` scoped to grant only
> this one role GUID at the account and its descendants. Nothing broader
> is required.

### Full-event-stream handling after granting

Role assignments take time to propagate. A valid dual-scope invocation
**may still emit an initial 401 (`model.call_failure` /
`transient_auth_error`) before an internal retry succeeds within the same
stream.** Therefore, **inspect the entire SSE event stream — never abort
on the first transient event.** Accept **recovered assistant output**
(`assistant.message` / `assistant.message_delta`) even after an earlier
401 envelope; only treat the invocation as failed if the complete stream
ends with no assistant output. The exact immediate-post-active readiness
envelope and bounded backoff are documented under § "Invoking the Agent".

### Cleanup / revocation

The two `Foundry User` grants are the only assignments you add. When
tearing down (or after a one-shot validation), revoke **strictly by the
assignment id you captured at create time** — deleting by
`--assignee`/`--role`/`--scope` can match and remove a pre-existing
standing grant you did not create:

```bash
az role assignment delete --ids "$account_assignment_id"
az role assignment delete --ids "$project_assignment_id"
```

Revocation is best-effort during teardown — a failed delete must not fail
an otherwise-successful run (the instance identity is deleted with the
agent version anyway). Never revoke an id you resolved as **pre-existing**
in the idempotent-create step above (`az role assignment list --assignee
... --role ... --scope ... --query "[0].id"` returned non-empty before you
created anything) — you did not create it, so it is not yours to delete.

### Deploying user

The **deploying user** still needs a role to create/update the agent:

| Role | Scope | Why |
|------|-------|-----|
| `Foundry Project Manager` | Foundry project | Data-plane permissions to create/update agents |

The project's managed identity must be able to pull from the registry. On a
direct-copy deploy to a registry that `azd` did not provision, deployment
failed with `[ImageError] Container registry authentication failed` until the
project managed identity was granted `AcrPull` on the registry (observed
2026-11-20); the guided `azd ai agent init --deploy-mode container` path wires
the registry for you (Azure/azure-dev #8981).

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| **401 on BYOK** | Wrong scope (`cognitiveservices.azure.com`) | Use `https://ai.azure.com/.default` |
| **`send_and_wait()` timeout** | 60s default + 120s gateway limit | Use Invocations protocol instead of ResponsesHostServer |
| **SSE response 0 chars** | Parser only captures `assistant.message` | Also capture `assistant.message_delta` as fallback |
| **Task Adherence eval 0%** | Using `gpt-5.4` as judge model | Use `gpt-5.4-mini` as judge |
| **Agent feels much slower than expected** | Still on SDK 1.x or `mode="coding-agent"` | Use SDK 2.0 `mode="empty"` — see § "Performance: SDK 2.0 in-process runtime" |
| **CopilotClient needs GITHUB_TOKEN** | No BYOK provider, or CAPI still enabled | Pass `inference.providers`/`models`, `github={"capi": {"enabled": False}}`, and `github={"use_logged_in_user": False}` on the client |
| **`mode is required and must be 'coding-agent' or 'empty'`** / `TypeError` on `CopilotClient()` | SDK 1.x constructor on 2.0 | `CopilotClient(mode="empty", runtime=...)` |
| **`CopilotClient(mode='empty') requires base_directory, session_fs, or a TcpRuntimeConnection`** | Empty mode without explicit storage | `RuntimeConnection.for_default(base_directory=...)` |
| **`create_session was called without available_tools`** | Empty mode needs an explicit allow-list on every create and resume | Pass `tools={"available_tools": [...]}` |
| **`Copilot runtime bundle is not cached in /home/session/.cache/... and automatic downloads are disabled`** (HTTP 502 `Failed to forward request` to the caller) | Runtime staged at build time under `/root/.cache`; Foundry runs with `HOME=/home/session` | Set `COPILOT_CLI_EXTRACT_DIR` before `python -m copilot download-runtime --in-process` (see § "Dockerfile") |
| **`[ImageError] Container registry authentication failed`** | Project managed identity cannot pull from a BYO registry | Grant `AcrPull` on the registry to the project managed identity, or use the guided init path |
| **`system_message` ignored** | Passed as string | Must be dict: `{"mode": "replace", "content": "..."}` |
| **Skills not loading** | Wrong option or path | Use absolute paths in `skills={"directories": [...]}` |
| **Agent crashes on startup** | Missing `azure-ai-agentserver-invocations` | Add it to dependencies (see `references/pyproject.toml`) |
| **Gateway timeout (502/504)** | Using Responses protocol for long queries | Switch to Invocations protocol |
| **401 after ~1h** | Static `bearer_token` on the provider | Use `bearer_token_provider`; the runtime calls it before each request |
| **Missing `[tool.setuptools] packages = []`** | uv resolution fails without it | Add to pyproject.toml (see `references/pyproject.toml`) |
| **CognitiveServices API version wrong** | Using old `2024-10-01` | Use `2025-10-01-preview` for agent management APIs |
| **Hooks fail on Windows** | `shell: sh` in a custom azd hook | Use `shell: pwsh` for cross-platform |
| **401 on real model inference** | Instance identity lacks `Foundry User` at the required scopes | Grant `Foundry User` (`53ca6127-db72-4b80-b1b0-d745d6d5456d`) to the **instance** identity at BOTH the Foundry account scope AND the project scope before invoking; project-only and account-only both 401. See § "Identity & RBAC for hosted agents" |
| **Immediate post-grant SSE `model.call_failure` 401 / `transient_auth_error`** | Instance grants are correct but role-assignment propagation has not completed | Inspect the full event stream and retry the same JSON positional `azd ai agent invoke` path with bounded 15-second backoff (max six); accept recovered assistant output later in the stream. A 401 that never recovers after both grants is a hard FAIL |
| **"responses protocol not declared" (bot 400)** | `azure.yaml`'s agent service only declares `invocations` but bot/CLI calls via Responses API (`oai.responses.create()`) | **Dual protocols don't work** — `InvocationAgentServerHost` only serves `/invocations`; the `/responses` path returns 404 even if a second protocol entry is declared. **Fix:** Rewrite the bot to POST directly to the Invocations SSE endpoint (or use `azd ai agent invoke --protocol invocations`) and parse `assistant.message` + `assistant.message_delta` events. **Alternative:** Use MAF runtime (ResponsesHostServer) which natively serves responses. |
| **ACR push 403 / RBAC error** | Deploying user lacks `AcrPush` on the target ACR | Assign `AcrPush` on the ACR, or use the guided `azd ai agent init --deploy-mode container` path, which wires the registry automatically (Azure/azure-dev #8981) |
| **Evals show no telemetry** | AppInsights not connected to Foundry account | Create `AppInsights` connection on the **account** (not project). Category: `AppInsights`, target: ARM resource ID, metadata: `ApiType: Azure`. `APPLICATIONINSIGHTS_CONNECTION_STRING` is reserved — platform injects it. |
| **Agent traces missing** | Agent identity lacks telemetry RBAC | Assign `Monitoring Metrics Publisher` on AppInsights to the agent identity (from `azd ai agent show`). Project MI needs `Log Analytics Data Reader` on Log Analytics workspace. |
| **gpt-4.1 encrypted content error** | gpt-4.1 deprecated, doesn't support encrypted content required by the Copilot SDK | Default to `gpt-5.4-mini` or `gpt-5.4`. Update `AZURE_AI_MODEL_DEPLOYMENT_NAME` in `azure.yaml` / azd env. |
| **`azd deploy` says "deployed in <1s" and nothing ships** | Copied a stripped-down `azure.yaml` missing the `services:` block | Use the canonical `references/yaml/azure.yaml` verbatim — see § "azure.yaml (unified GA deployment)" |

---

## Architecture Comparison

```
MAF (Responses Protocol):
  container.py → Agent + FoundryChatClient + ResponsesHostServer → port 8088
    └── Request/response: caller waits for full response
    └── Timeout: ~120s (Foundry gateway)

Copilot SDK 2.0 (Invocations Protocol):
  container.py → CopilotClient(mode="empty") + InvocationAgentServerHost → port 8088
    └── SSE streaming: events flow continuously
    └── Timeout: unlimited (connection kept alive by events)
```

### Decision Matrix

| Factor | Choose MAF | Choose Copilot SDK 2.0 |
|--------|-----------|------------------------|
| Tool loop duration | <120s | >120s |
| Custom tools | ✅ `@tool` | ✅ `@define_tool` + `tools.available_tools` |
| Foundry Toolbox | ✅ `MCPStreamableHTTPTool` (was `get_toolbox()`, removed 1.3.0) | ❌ Not available (remote MCP via `mcp.servers`) |
| Streaming output | ❌ Response only | ✅ Event stream |
| Progressive skills | ✅ `SkillsProvider.from_paths()` (or legacy concat) | ✅ `skills.directories` / `skills.provider` |
| MCP tools | `client.get_mcp_tool()` | `mcp.servers` + `mcp:` allow-list |
| Tool governance | Middleware | `hooks.handlers.on_pre_tool_use` |
| Auth complexity | Low (DAC → FoundryChatClient) | Medium (named BYOK provider + token callback) |
| Packages | Stable releases | Stable SDK (`microsoft-copilot-sdk` 2.0); agentserver packages stable 1.3/2.3 |
| Deploy shape | Unified `azure.yaml` (`foundry-hosted-agents`) | Unified `azure.yaml` (this skill) — same GA shape, different protocol/runtime |

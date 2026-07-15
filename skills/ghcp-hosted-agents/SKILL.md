---
name: ghcp-hosted-agents
description: >
  Deploy Foundry hosted agents using GitHub Copilot SDK (GHCP) with BYOK
  authentication and Invocations protocol. Alternative to MAF (Agent +
  FoundryChatClient + ResponsesHostServer). Use when you need streaming SSE
  output, progressive skill discovery, or long tool loops (>120s) that hit
  Foundry gateway timeout with Responses protocol.
  USE FOR: ghcp sdk, copilot sdk, github copilot agent, CopilotClient,
  InvocationAgentServerHost, BYOK, bring your own key, invocations protocol,
  SSE streaming agent, long running agent, send_and_wait timeout,
  ghcp hosted agent, copilot client foundry.
  DO NOT USE FOR: MAF agents (use foundry-hosted-agents), prompt agents,
  declarative agents, general Azure deploy.
metadata:
  version: "2.0.2"
---

# GHCP SDK Hosted Agents on Foundry

Deploy Foundry hosted agents using the **GitHub Copilot SDK** with BYOK
(Bring Your Own Key) authentication. No `GITHUB_TOKEN` required. Uses the
**Invocations protocol** (GA, version `2.0.0`) with SSE streaming for
unlimited tool-loop duration.

> **GA migration (v2.0.0).** This skill now uses the unified single-file
> `azure.yaml` deploy shape shared with `foundry-hosted-agents` — the old
> two-file `agent.yaml` + separately-wired `azure.yaml` contract, the
> remote-build/manual `services:` wiring, the tenant-ID-env deploy hook,
> and the manual account-scope `Foundry User` role grant are all retired.
> See § "azure.yaml (unified GA deployment)" and § "Identity & RBAC for
> hosted agents" below.

## When to Use GHCP SDK Instead of MAF

| Consideration | MAF | GHCP SDK |
|---------------|-----|----------|
| **Auth** | `DefaultAzureCredential` → `FoundryChatClient` | BYOK: `DefaultAzureCredential` → bearer token |
| **Protocol** | Responses API (request/response) | Invocations (SSE streaming) |
| **Tool loop limit** | ~120s (Foundry gateway timeout) | ♾️ (SSE keeps connection alive) |
| **Per-query overhead** | Low (1-3 internal turns) | High (20-34 internal tool calls per query) |
| **Skill discovery** | `SkillsProvider.from_paths()` (recommended) **OR** inline concat (legacy) | `SkillsProvider` (default) |
| **Custom tools** | `@tool` decorator | Not supported (use MCP servers instead) |
| **Toolbox** | `MCPStreamableHTTPTool` (was `client.get_toolbox()`, removed 1.3.0) | Not directly available |
| **Maturity** | Production-proven | Validated (identical eval scores) |

**Use GHCP SDK when:**
- Slow tools mask the per-query overhead: web scraping, long-running tools, or multi-site scans.
- You need streaming progress events to the caller for workflows that run beyond the ~120s Responses gateway limit.
- The workload looks like **bat-scraper**: Playwright/tool calls take 30-60s each, so GHCP SDK orchestration overhead is acceptable.

**Use MAF when:**
- Tools are fast: data queries, MCP retrieval, or single-shot tools where orchestration overhead dominates latency.
- You need the faster runtime path; field measurements show MAF at **~19s** vs GHCP SDK at **>220s** for the same fast-MCP workload (~10x faster).
- Agent needs custom `@tool` functions, Foundry Toolbox (`web_search`, `code_interpreter`), or simpler deployment.

---

## ⚠️ Performance Caveat: Per-Query Overhead

Each `CopilotClient` query generates **20-34 internal tool calls** for planning,
skill discovery, tool selection, and related orchestration.
That happens regardless of how many user-facing tool calls the agent actually makes.
The overhead lives in `CopilotClient` itself; `SkillsProvider` is **NOT** the cause.
Removing `SkillsProvider` does not eliminate the extra internal turns.
Field measurement on an identical agent (`gpt-5.4`, same MCP tool set, same query)
ran in **~19s on MAF** but **>220s on GHCP SDK** when MCP tools were fast.
The overhead is masked when tools are slow: bat-scraper Playwright calls take
30-60s each, so 20 internal calls vanish in the noise.
Decision rule: if your slowest tool is <2s, you almost certainly want MAF.
If your slowest tool is >30s and you need streaming progress events to the caller,
GHCP SDK is the better fit.

> **Note on `SkillsProvider` cost (both runtimes).** `SkillsProvider` is
> **not** GHCP-only — MAF supports it equally well via
> `context_providers=[skills_provider]` (see `foundry-hosted-agents`
> § Skill Loading). On both runtimes, `SkillsProvider` itself adds only
> **+1 `load_skill` round-trip per skill the agent activates per query**
> (typically 1-3 per query). The 20-34-call overhead above is the
> `CopilotClient` runtime, an entirely separate concern.

---

## Runtime Pattern (GHCP SDK + Invocations)

**Copy the reference template** at `references/container.py` into the project root.
Then adapt `_load_mcp_servers()` for your MCP server configuration.

The template provides:
1. `_init_byok()` / `_get_provider()` — BYOK auth with `DefaultAzureCredential`
2. `_ensure_session()` — Creates/resumes `CopilotClient` session with provider, skills, MCP
3. `_stream_response()` — Subscribes to session events, yields SSE
4. `handle_invoke()` — `@app.invoke_handler` that returns `StreamingResponse`

```
container.py → CopilotClient + InvocationAgentServerHost → port 8088
  ├── BYOK auth (ai.azure.com scope)
  ├── Skills via skill_directories parameter
  ├── MCP servers via mcp_servers parameter
  └── SSE streaming (no timeout on long tool loops)
```

**Key points:**
- `FOUNDRY_PROJECT_ENDPOINT` is **injected by the platform** — never declare it
  under the `azure.yaml` agent service's `environmentVariables` list (see
  § "azure.yaml (unified GA deployment)")
- BYOK scope is `https://ai.azure.com/.default` — NOT `cognitiveservices.azure.com`
- Token is static per session — `_get_provider()` mints fresh token each session creation
- `working_directory` should be `$HOME` (hosted agents sandbox filesystem at home dir)
- `system_message` requires dict format: `{"mode": "replace", "content": "..."}`
- `PermissionHandler.approve_all` auto-approves tool calls (required for unattended agents)

---

## Why Invocations Protocol (Not Responses)

The GHCP SDK can also run behind `ResponsesHostServer` using `GitHubCopilotAgent`:

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
server type the GHCP SDK runtime ships with; serving Responses requires
switching to the MAF runtime (`ResponsesHostServer`) entirely. External
callers (bot, eval scripts) must POST to the Invocations SSE endpoint
directly, or use `azd ai agent invoke --protocol invocations`. If you need
`oai.responses.create()` for a Teams bot, use MAF runtime instead.

---

## pyproject.toml

**Copy** `references/pyproject.toml` into your project root and update `name` and `version`.

**Notes:**
- `github-copilot-sdk` provides `CopilotClient`, session management, event types
- `azure-ai-agentserver-invocations` provides `InvocationAgentServerHost`
- `azure-ai-agentserver-core` pinned EXACT (`==2.0.0b7`) — it's a transitive dep of `-invocations` declared as `>=2.0.0b7` (unbounded upper); the exact pin stops a future core `b8+` from silently breaking fresh container builds
- `azure-identity` pinned to avoid pulling beta versions
- `prerelease = "if-necessary-or-explicit"` needed for beta agentserver package

---

## Dockerfile

**Copy** `references/Dockerfile` into your project root. No changes needed for most agents.

---

## BYOK Authentication Deep Dive

BYOK (Bring Your Own Key) lets `CopilotClient` use your Foundry model deployment
instead of GitHub's hosted models. No `GITHUB_TOKEN` needed.

### How It Works

```
CopilotClient.create_session(provider={...})
  └── Routes LLM calls to your Foundry project endpoint
      └── Uses bearer token from DefaultAzureCredential
          └── Scope: https://ai.azure.com/.default
```

### Provider Configuration

`copilot.ProviderConfig` is a `TypedDict` — at runtime it produces a
plain `dict`, so the "class" form and the "dict" form below are byte-identical
runtime objects. Use the class form when you want IDE / typing help; use the
dict form when you want a one-liner.

What actually matters is the **values**: `type="azure"` + bare endpoint is the
PRIMARY shape (matches the official Microsoft sample, ~2-3× faster); the
legacy `type="openai"` + `/openai/v1/` is still accepted for backward compat.

```python
# RECOMMENDED — class form (TypedDict), gives you typing + IDE completion.
from copilot import ProviderConfig

provider = ProviderConfig(
    type="azure",                          # SDK adds api-version itself
    base_url=FOUNDRY_ENDPOINT,             # BARE project endpoint — no /openai/v1/
    wire_api="responses",
    bearer_token=token.token,              # from DefaultAzureCredential
)
```

```python
# LEGACY — same wire shape, type='openai' kept for backward compat (2-3× slower).
provider = {
    "type": "openai",
    "base_url": f"{FOUNDRY_ENDPOINT}/openai/v1/",  # must end with /openai/v1/
    "bearer_token": token.token,
    "wire_api": "responses",
}
```

### Provider shape decision matrix

Measured against `gpt-5.4-mini` on a live Foundry project (May 2026):

| `type` | `base_url` suffix | Result | Latency |
|--------|-------------------|--------|---------|
| `"azure"` | bare endpoint | ✅ **Recommended** | ~2.6s |
| `"azure"` | `/openai/v1/` | ✅ Works | ~7.9s |
| `"openai"` | `/openai/v1/` | ✅ Legacy compat | ~6.9s |
| `"openai"` | bare endpoint | ❌ `400 Missing api-version` | n/a |

`github-copilot-sdk` `1.0.1` (GA, this skill) and prior `0.3.0` / `1.0.0b*`
preview lines all accept both `type="azure"` and the legacy
`type="openai"` shapes; the legacy dict form is preserved across releases
for backward compatibility. The 1.0 GA constructor is flat — pass
`github_token=...` directly to `CopilotClient(...)` (no `SubprocessConfig`
wrapper; `auto_start` kwarg removed — call `await client.start()` explicitly).
The public import surface as of the GA release is
`from copilot import CopilotClient, PermissionHandler, ProviderConfig` and
`from copilot.session_events import SessionEventType` (matches the official
Microsoft sample's `main.py`) — see `references/container.py`.

### Common BYOK Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Wrong scope | 401 Unauthorized | Use `ai.azure.com` not `cognitiveservices.azure.com` |
| `type="openai"` + bare endpoint | `400 Missing api-version` | Either switch to `type="azure"` + bare, or append `/openai/v1/` |
| Token not refreshed | 401 after ~1h | Mint fresh token per session in `_get_provider()` |
| Permission error during deploy or invoke | 403 / `PermissionDenied` | This is a hard FAIL, not a role-grant opportunity — the hosted agent's identity has implicit access to model inferencing and session storage by default (see § "Identity & RBAC for hosted agents"). Investigate the actual cause; do not grant roles to route around it |

---

## CopilotClient Session Parameters

```python
# Recommended pattern (matches official Microsoft sample): explicit start().
# As of github-copilot-sdk 1.0 GA, CopilotClient takes flat kwargs — no
# SubprocessConfig wrapper, no auto_start. Construct, then await start().
client = CopilotClient()
await client.start()

session = await client.create_session(
    provider=provider,                    # ProviderConfig OR dict — see "Provider Configuration"
    model="gpt-5.4-mini",                 # Foundry model deployment name
    system_message={                      # MUST be dict, not string
        "mode": "replace",
        "content": "You are a helpful assistant.",
    },
    skill_directories=["/app/skills"],    # Paths to SKILL.md directories
    mcp_servers=[                         # MCP server configs (list[dict] or dict[str, dict])
        {"name": "playwright", "url": "https://my-mcp.azurecontainerapps.io/mcp"},
    ],
    working_directory=str(Path.home()),   # Must be $HOME for hosted agents
    streaming=True,                       # Enable streaming events
    on_permission_request=PermissionHandler.approve_all,  # Auto-approve tools
)
```

### Session Event Types

| Event Type | Meaning | Action |
|------------|---------|--------|
| `SESSION_IDLE` | Response complete | Stop streaming, yield `done` event |
| `SESSION_ERROR` | Agent error | Yield error event, stop |
| `assistant.message` | Final assistant response | Contains full response text |
| `assistant.message_delta` | Streaming content chunk | Accumulate for progressive display |
| `assistant.streaming_delta` | Raw streaming delta | Lower-level than message_delta |
| `assistant.reasoning` | Reasoning trace | Full reasoning block |
| `assistant.reasoning_delta` | Reasoning chunk | Streaming reasoning |
| `tool.execution_start` | Tool call started | Log for debugging |
| `tool.execution_complete` | Tool call finished | Log for debugging |
| `assistant.turn_start` | New turn | Track turn count |
| `assistant.turn_end` | Turn complete | May have more turns |

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
briefly return an HTTP-200 SSE stream containing `model.call_failure` with
`statusCode: 401`, `PermissionDenied`, and `transient_auth_error` while the
platform's implicit agent permission finishes propagating. Retry the **same
JSON positional invoke path** with bounded backoff (six attempts, 15 seconds
between attempts). Do not switch invocation methods and do not add a role
grant. A nonzero CLI exit or a different terminal SSE error remains a hard
failure.

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
`foundry-hosted-agents` uses, adapted for the GHCP SDK's Invocations
protocol instead of MAF's Responses protocol.

> **MUST:** Copy verbatim from [`references/yaml/azure.yaml`](references/yaml/azure.yaml). Do NOT redefine inline — the validator enforces single-source-of-truth. That file is the canonical `azure.ai.project` + `azure.ai.agent` service pair for a container-built GHCP SDK hosted agent connecting to a **pre-provisioned** Foundry project.

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
| `kind: hosted` on the `azure.ai.agent` service | Marks it as a containerized/source-built hosted agent (as opposed to a Foundry Agent Service prompt agent) |
| Protocol `invocations`, version `2.0.0` | Current GA protocol + version for the GHCP SDK's `InvocationAgentServerHost`. Do NOT add a `responses` protocol entry — see § "Why Invocations Protocol (Not Responses)" |
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

`azd ai agent` creates a dedicated Microsoft Entra agent identity per
hosted agent at deploy time (visible via `azd ai agent show`) — this is
what your running container uses to call models and tools.

### Default case: no agent role assignment needed

As of the GA hosted-agent permissions model (Azure/azure-dev PR #8941,
merged 2026-07-03), the Foundry service grants the agent identity its
required permissions **internally** — model inferencing through the
project endpoint and session storage read/write are available by
default, with no client-side role assignment step.

**No explicit role assignment or additional configuration is needed for
the standard BYOK case documented in this skill.** There is no postdeploy
RBAC-grant hook to run, and no manual account-scope `Foundry User` grant
for the agent identity. If you were relying on a manual account-scope
`Foundry User` grant from a pre-GA build of this skill, delete that step —
it's not just unnecessary now, the client-side assignment attempt is
itself what the GA change removed (it used to fail noisily when the
deploying user lacked `Microsoft.Authorization/roleAssignments/write`).

**A permission error during deploy or invoke is a hard FAIL, not a
role-grant opportunity.** Investigate the actual cause (wrong scope,
expired credential, wrong project) — do not attempt to work around it
with an ad hoc role assignment.

**Deploying user** still needs a role to create/update the agent:

| Role | Scope | Why |
|------|-------|-----|
| `Foundry Project Manager` | Foundry project | Data-plane permissions to create/update agents |

`azd` handles the ACR pull role (**Container Registry Repository
Reader** on the project's managed identity) automatically as part of
`azd deploy`.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| **401 on BYOK** | Wrong scope (`cognitiveservices.azure.com`) | Use `https://ai.azure.com/.default` |
| **`send_and_wait()` timeout** | 60s default + 120s gateway limit | Use Invocations protocol instead of ResponsesHostServer |
| **SSE response 0 chars** | Parser only captures `assistant.message` | Also capture `assistant.message_delta` as fallback |
| **Task Adherence eval 0%** | Using `gpt-5.4` as judge model | Use `gpt-5.4-mini` as judge |
| **Agent feels much slower than expected** | CopilotClient internal-turn overhead (20-34 internal calls per query) | Use MAF runtime instead — see `## ⚠️ Performance Caveat: Per-Query Overhead` |
| **CopilotClient needs GITHUB_TOKEN** | Not using BYOK provider | Pass `provider` dict to `create_session()` |
| **`system_message` ignored** | Passed as string | Must be dict: `{"mode": "replace", "content": "..."}` |
| **Skills not loading** | Wrong path format | Use absolute paths in `skill_directories` list |
| **Agent crashes on startup** | Missing `azure-ai-agentserver-invocations` | Add to dependencies, use `prerelease = "if-necessary-or-explicit"` |
| **Gateway timeout (502/504)** | Using Responses protocol for long queries | Switch to Invocations protocol |
| **Token expired during long query** | BYOK token static per session | Token has ~1h validity; for longer sessions, create new session |
| **Token expired during eval runs** | Long eval runs (many scenarios) exhaust the BYOK token | Refresh the provider token per invocation: call `_get_provider()` fresh before each `_ensure_session()`, or create a new session every ~30 min |
| **Container can't resolve packages** | pip doesn't handle pre-release deps | Use `uv` with pre-release settings in `[tool.uv]` |
| **Missing `[tool.setuptools] packages = []`** | uv resolution fails without it | Add to pyproject.toml (see `references/pyproject.toml`) |
| **CognitiveServices API version wrong** | Using old `2024-10-01` | Use `2025-10-01-preview` for agent management APIs |
| **Hooks fail on Windows** | `shell: sh` in a custom azd hook | Use `shell: pwsh` for cross-platform |
| **Permission error on deploy or invoke** | Attempting to work around it with a manual role grant | It's a hard FAIL by design — see § "Identity & RBAC for hosted agents". Investigate the real cause instead |
| **Immediate post-deploy SSE `model.call_failure` 401 / `transient_auth_error`** | Agent version is active but implicit model permission has not finished propagating | Retry the same JSON positional `azd ai agent invoke` path with bounded 15-second backoff (max six); do not grant roles. Any different permission envelope remains a hard FAIL |
| **"responses protocol not declared" (bot 400)** | `azure.yaml`'s agent service only declares `invocations` but bot/CLI calls via Responses API (`oai.responses.create()`) | **Dual protocols don't work** — `InvocationAgentServerHost` only serves `/invocations`; the `/responses` path returns 404 even if a second protocol entry is declared. **Fix:** Rewrite the bot to POST directly to the Invocations SSE endpoint (or use `azd ai agent invoke --protocol invocations`) and parse `assistant.message` + `assistant.message_delta` events. **Alternative:** Use MAF runtime (ResponsesHostServer) which natively serves responses. |
| **ACR push 403 / RBAC error** | Deploying user lacks `AcrPush` on the target ACR | Assign `AcrPush` on the ACR, or use the guided `azd ai agent init --deploy-mode container` path, which wires the registry automatically (Azure/azure-dev #8981) |
| **Evals show no telemetry** | AppInsights not connected to Foundry account | Create `AppInsights` connection on the **account** (not project). Category: `AppInsights`, target: ARM resource ID, metadata: `ApiType: Azure`. `APPLICATIONINSIGHTS_CONNECTION_STRING` is reserved — platform injects it. |
| **Agent traces missing** | Agent identity lacks telemetry RBAC | Assign `Monitoring Metrics Publisher` on AppInsights to the agent identity (from `azd ai agent show`). Project MI needs `Log Analytics Data Reader` on Log Analytics workspace. |
| **gpt-4.1 encrypted content error** | gpt-4.1 deprecated, doesn't support encrypted content required by GHCP SDK | Default to `gpt-5.4-mini` or `gpt-5.4`. Update `AZURE_AI_MODEL_DEPLOYMENT_NAME` in `azure.yaml` / azd env. |
| **`azd deploy` says "deployed in <1s" and nothing ships** | Copied a stripped-down `azure.yaml` missing the `services:` block | Use the canonical `references/yaml/azure.yaml` verbatim — see § "azure.yaml (unified GA deployment)" |

---

## Architecture Comparison

```
MAF (Responses Protocol):
  container.py → Agent + FoundryChatClient + ResponsesHostServer → port 8088
    └── Request/response: caller waits for full response
    └── Timeout: ~120s (Foundry gateway)

GHCP SDK (Invocations Protocol):
  container.py → CopilotClient + InvocationAgentServerHost → port 8088
    └── SSE streaming: events flow continuously
    └── Timeout: unlimited (connection kept alive by events)
```

### Decision Matrix

| Factor | Choose MAF | Choose GHCP SDK |
|--------|-----------|----------------|
| Tool loop duration | <120s | >120s |
| Custom `@tool` functions | ✅ Required | ❌ Not supported |
| Foundry Toolbox | ✅ `MCPStreamableHTTPTool` (was `get_toolbox()`, removed 1.3.0) | ❌ Not available |
| Streaming output | ❌ Response only | ✅ Event stream |
| Progressive skills | ✅ `SkillsProvider.from_paths()` (or legacy concat) | ✅ `SkillsProvider` |
| MCP tools | `client.get_mcp_tool()` | `mcp_servers` parameter |
| Auth complexity | Low (DAC → FoundryChatClient) | Medium (BYOK token minting) |
| Packages | Stable releases | Pre-release beta |
| Deploy shape | Unified `azure.yaml` (`foundry-hosted-agents`) | Unified `azure.yaml` (this skill) — same GA shape, different protocol/runtime |

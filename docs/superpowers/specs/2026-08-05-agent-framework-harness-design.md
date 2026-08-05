# Agent Framework Harness Skill - Design

- **Date:** 2026-08-05
- **Status:** Approved design; implementation not started
- **Proposed skill:** `agent-framework-harness`
- **Initial skill version:** `1.0.0`
- **Language:** Python
- **Primary upstream:** Microsoft Agent Framework
- **PR shape:** one new standalone skill plus required catalog integration and generated docs

This document is the complete design deliverable. It intentionally does not
create `skills/agent-framework-harness/` or change any existing skill.

---

## 1. Decision and naming

Create a standalone skill named `agent-framework-harness`.

The name is intentionally not `foundry-agent-harness`. The
`create_harness_agent` factory is part of the Microsoft Agent Framework Python
runtime and accepts any compatible chat client. Microsoft Foundry is a primary
recipe and hosting target, not the ownership boundary of the factory.

### Quick decision table

| Need | Use |
|---|---|
| Build an opinionated, batteries-included Agent Framework `Agent` with plan/execute modes, todos, compaction, memory, approval UX, optional looping, shell, or background agents | `agent-framework-harness` |
| Package, deploy, version, roll out, authenticate, or troubleshoot a Foundry hosted container | [`foundry-hosted-agents`](../../../skills/foundry-hosted-agents/SKILL.md) |
| Enforce deterministic, non-bypassable action policy, capability allow/deny, audit integrity, or sandbox governance | [`foundry-agt`](../../../skills/foundry-agt/SKILL.md) |
| Publish or consume centrally distributed `SKILL.md` content through the Foundry Skills REST API | [`foundry-skill-catalog`](../../../skills/foundry-skill-catalog/SKILL.md) |
| Score quality, run regressions, or own general evaluation workflows | [`foundry-evals`](../../../skills/foundry-evals/SKILL.md) or the applicable evaluation skill |

### Ownership boundary

`agent-framework-harness` owns:

- `create_harness_agent`;
- the factory's internal provider, tool, middleware, and history pipeline;
- actual Python defaults and disable/opt-in switches;
- plan and execute modes;
- persistent todos and `AgentSession` recovery;
- context compaction;
- session-scoped file memory;
- shared file access;
- tool approval UX and standing approvals;
- bounded autonomous looping;
- shell and background-agent composition;
- wiring the returned `Agent` into `ResponsesHostServer`.

It does not own:

- deployment, RBAC, identity grants, containers, ACR, `azure.yaml`, rollout, or
  lifecycle management;
- deterministic governance, action policy, audit, or sandbox ownership;
- Foundry Skills REST publication and distribution;
- general evaluation design.

Native Harness approval is a user-experience gate. It is not a policy engine,
an authorization system, a non-bypassable governance boundary, or an audit
control.

---

## 2. Architecture and internal factory pipeline

Agent Harness is runtime scaffolding, not hosting. The factory returns a normal
Agent Framework `Agent`. Hosting is a later adapter step.

```text
Compatible chat client
  |
  v
create_harness_agent(...)
  |
  +-- instructions
  |     default harness instructions + agent_instructions
  |
  +-- context providers, in order
  |     history
  |     conditional compaction
  |     todo
  |     mode
  |     file memory
  |     optional shared file access
  |     optional skills
  |     optional background agents
  |     optional shell environment
  |     caller-supplied providers
  |
  +-- tools
  |     conditional hosted web search
  |     optional shell tool
  |     caller-supplied tools
  |
  +-- middleware, outermost first
  |     optional bounded loop
  |     default tool approval
  |     always-on message injection
  |     caller-supplied middleware
  |
  +-- Agent(
          require_per_service_call_history_persistence=True,
          compaction_strategy=<before-call strategy>,
          default_options=<merged options>
      )
  |
  +--> local caller: agent.run(..., session=session)
  |
  +--> hosted caller: ResponsesHostServer(agent).run()
```

### Pipeline rules the skill must teach

1. The default history provider is `InMemoryHistoryProvider`.
2. Per-service-call history persistence is always enabled on the returned
   `Agent`; callers still own durable storage and recovery of `AgentSession`.
3. The default token-budget compaction strategy is created only when both
   `max_context_window_tokens` and `max_output_tokens` are supplied.
4. A custom before or after strategy can activate its own compaction phase
   without token-budget parameters. `disable_compaction=True` overrides both
   custom and default strategies.
5. Before-call compaction is installed as the Agent's `compaction_strategy`;
   after-call compaction is installed through `CompactionProvider`.
6. Tool approval is outside function invocation and requires an
   `AgentSession`. A pending approval stops autonomous looping and returns
   control to the caller.
7. Looping is outermost so every pass is a complete run with history,
   providers, approval, and telemetry.
8. `ResponsesHostServer` receives the already-built `Agent`; it does not build
   the Harness pipeline.

---

## 3. Default, opt-in, and experimental feature matrix

The implementation must derive this table from the published Python signature
and source at every pin refresh. Documentation prose alone is not sufficient.

| Capability | 1.13.0 behavior | Maturity and guidance |
|---|---|---|
| Function invocation | Always wired by `Agent` | Released |
| Per-service-call history persistence | Always enabled | Released; not durable across process loss unless `AgentSession` is persisted |
| Todo provider | Default on; disable with `disable_todo=True` | Released |
| Plan/execute mode provider | Default on; initial built-in mode is `plan`; disable with `disable_mode=True` | Released |
| File memory | Default on; session-scoped store defaults to `{cwd}/agent-file-memory` | Released; make the filesystem side effect explicit |
| Compaction | Conditional; inactive with bare factory defaults | Released; both token budgets or custom strategies are required |
| Web search | Conditional default on: auto-added only when the client implements `SupportsWebSearchTool`; otherwise a warning is logged | Released; set `disable_web_search=True` for deterministic or offline recipes |
| Tool approval middleware | Default on; coordinates queued approvals and session-backed "always approve" rules | Released UX gate; `disable_tool_auto_approval=False` does not blanket-approve tools; requires `AgentSession` |
| Heuristic auto-approval callbacks | None unless `auto_approval_rules` is supplied | Opt-in; rules must inspect arguments where risk depends on arguments |
| Message injection | Always on and no-op when the session queue is empty | Released |
| OpenTelemetry provider name | Set by the factory | Released; telemetry destination and sensitive-data settings remain caller-owned |
| Shared file access | Opt-in through `file_access_store`; there is no Python 1.13.0 `disable_file_access` parameter | Experimental; read and write tools require approval by default |
| Skills | Opt-in through `skills_provider` and/or `skills_paths` | Released; external sources are untrusted input |
| Background agents | Opt-in through `background_agents` | Experimental; delegated agents and returned content must be trusted |
| Shell | Opt-in through `shell_executor`; also requires a client implementing `SupportsShellTool` | Pre-release `agent-framework-tools`; experimental |
| Autonomous looping | Opt-in through `loop_should_continue` | Experimental; default library cap is 10, but skill recipes must pass an explicit positive cap |
| Caller providers and middleware | Opt-in | Advanced extension surface; preserve built-in ordering |

Two defaults require especially precise wording:

- Web search is not unconditionally present. `disable_web_search=False` is the
  default, but the tool is added only for a client that advertises
  `SupportsWebSearchTool`.
- Tool approval middleware is present by default, but generic heuristic
  callbacks are not. `auto_approval_rules=None` means no caller-supplied
  heuristic rule. File-access tools also require approval by default unless the
  caller explicitly changes their approval flags.

---

## 4. Canonical local Python recipe

The future skill must keep the complete runnable recipe in
`references/python/local_harness.py` and link to it from `SKILL.md`; it must not
duplicate the full code body inline.

The canonical shape is:

```python
import asyncio
import os
from pathlib import Path

from agent_framework import FileSystemAgentFileStore, create_harness_agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential


async def main() -> None:
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=AzureCliCredential(),
    )

    agent = create_harness_agent(
        client=client,
        name="local-harness",
        agent_instructions="Plan carefully, verify tool results, and report the final outcome.",
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        file_memory_store=FileSystemAgentFileStore(
            (Path.cwd() / ".agent-memory").resolve()
        ),
        disable_web_search=True,
    )

    session = agent.create_session()
    response = await agent.run(
        "Create a short plan for validating this harness configuration.",
        session=session,
    )
    print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
```

Recipe requirements:

- pass an `AgentSession` because default approval middleware and provider state
  are session-backed;
- supply both token budgets so compaction is actually active;
- make the file-memory location visible rather than silently writing to an
  unknown working directory;
- disable web search in the baseline recipe so a local smoke does not
  unexpectedly call a hosted tool;
- do not enable file access, shell, background agents, or looping in the
  baseline;
- state that `FoundryChatClient` can be replaced by any compatible chat client.

The local recipe uses Foundry because this catalog is Azure-first. The skill
name and architecture remain provider-neutral.

---

## 5. Canonical Foundry Hosted recipe

The future skill must keep the complete hosted runtime recipe in
`references/python/hosted_harness.py`. Deployment, `azure.yaml`, RBAC,
container, and rollout instructions remain links to
`foundry-hosted-agents`.

```python
import os

from agent_framework import create_harness_agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential


def main() -> None:
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),
    )

    agent = create_harness_agent(
        client=client,
        name="hosted-harness",
        agent_instructions="Complete the caller's task and return a concise result.",
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        disable_mode=True,
        disable_file_memory=True,
        disable_web_search=True,
        default_options={"store": False},
    )

    ResponsesHostServer(agent).run()


if __name__ == "__main__":
    main()
```

Hosted-recipe rules:

1. `create_harness_agent` still owns runtime composition.
2. `ResponsesHostServer` owns the Responses protocol adapter and HTTP host.
3. `default_options={"store": False}` is required for the current
   Foundry-hosting pattern because the hosting infrastructure manages
   conversation history.
4. Disable interactive mode in the baseline headless recipe. A hosted
   application may re-enable mode only when its caller protocol explicitly
   supports plan approval and mode transitions.
5. Disable default file memory in the baseline hosted recipe. Re-enable it only
   with a deliberate durable-store and tenant-partitioning design.
6. Do not add deployment or RBAC commands here. Link to
   `foundry-hosted-agents`.

Product and package status must remain separate:

| Surface | Status source and current design position |
|---|---|
| Agent Harness factory | Released in stable `agent-framework-core` 1.13.0 |
| `agent-framework-foundry-hosting` adapter | `1.0.0b260730` beta prerelease; exact pin required |
| Foundry hosted container service | Separate product lifecycle; the current `foundry-hosted-agents` contract treats container deployment as GA and source-code deployment as preview |

The hosting adapter's beta version does not make the Hosted Agents service
beta, and the service's lifecycle does not make the Python adapter stable.

---

## 6. Safe plan-to-execute pattern

Plan mode must remain interactive. Autonomous looping must be restricted to
execute mode and bounded by an explicit positive iteration cap.

```python
from agent_framework import (
    create_harness_agent,
    set_agent_mode,
    todos_remaining,
    todos_remaining_message,
)

agent = create_harness_agent(
    client=client,
    max_context_window_tokens=128_000,
    max_output_tokens=16_384,
    loop_should_continue=todos_remaining(looping_modes=["execute"]),
    loop_next_message=todos_remaining_message,
    loop_max_iterations=10,
    disable_web_search=True,
)

session = agent.create_session()
set_agent_mode(session, "plan")

plan_response = await agent.run(
    "Plan the requested work. Do not execute until the caller approves the plan.",
    session=session,
)

# The host displays plan_response and obtains explicit caller approval here.

set_agent_mode(session, "execute")
result = await agent.run(
    "Execute the approved plan and complete the remaining todos.",
    session=session,
)
```

The future reference must represent the approval step as a real host callback
or explicit function boundary, not a comment that an autonomous agent can skip.
The abbreviated block above defines the API shape; the canonical reference
must provide an `approve_plan: Callable[[str], Awaitable[bool]]` boundary and
must not call `set_agent_mode(session, "execute")` when approval returns false.

Safety requirements:

- never use `loop_max_iterations=None` in a skill recipe;
- keep the predicate scoped to `looping_modes=["execute"]`;
- stop and return control when a tool approval is pending;
- use `set_agent_mode` instead of mutating `session.state`;
- persist the approved plan and todos before switching modes;
- treat the cap as a cost and runaway guard, not proof that the work is safe;
- do not describe an LLM judge or todo predicate as deterministic governance.

---

## 7. Session persistence and recovery

The Harness persists history after each service call into `AgentSession`, but
the default history provider is in-memory. Process recovery therefore requires
the host to persist the full session object:

```python
from agent_framework import AgentSession

serialized = session.to_dict()
# Store serialized in a durable, tenant-partitioned session store.
restored = AgentSession.from_dict(serialized)
```

The skill must state all of the following:

- persist the full opaque session, not only message text;
- restore with the same agent, provider, and middleware configuration;
- partition storage by authenticated tenant and user;
- authorize the caller before loading a session identifier;
- do not accept arbitrary serialized session state from an untrusted caller;
- do not mutate provider-owned state keys directly;
- use one owner for conversation persistence. In the Foundry Hosted recipe,
  keep `store=False` and let the host manage Responses conversation history.

File memory and session serialization solve different problems. File memory
stores session-scoped notes and artifacts; `AgentSession` stores provider,
approval, mode, todo, history, and middleware state needed to resume the
pipeline.

---

## 8. Harness versus Hosted Agents versus AGT

| Concern | Agent Framework Harness | Foundry Hosted Agents | Agent Governance Toolkit |
|---|---|---|---|
| Primary job | Compose an agentic runtime around a chat client | Host, scale, identify, deploy, and expose an agent | Enforce deterministic action policy and produce governance evidence |
| Main object | `Agent` returned by `create_harness_agent` | Container/runtime plus Responses or Invocations endpoint | Middleware or sidecar policy enforcement |
| Plan, todos, compaction, memory | Owned | Not supplied by hosting itself | Not owned |
| Tool approval | Session-backed UX prompts and standing approvals | Transports approval content; no policy semantics by itself | Deterministic allow, deny, sanitize, escalate, and audit |
| Looping | Optional Harness middleware | Runs whatever the hosted Agent implements | Can gate actions inside a loop but does not create the loop |
| Shell | Optional executor and environment provider | Supplies compute boundary only when configured | Owns policy/sandbox governance, not shell convenience |
| Persistence | `AgentSession`, history provider, file memory | Hosted session and conversation lifecycle | Audit and policy state |
| Deployment and RBAC | Excluded | Owned by `foundry-hosted-agents` | Excluded |
| Security boundary | No | Hosting isolation is a separate platform concern | Yes for the policy surfaces explicitly configured |

Use all three when needed:

```text
Harness Agent -> AGT middleware/policy -> ResponsesHostServer
              -> Foundry hosted runtime, identity, scale, and lifecycle
```

---

## 9. Failure modes and security callouts

| Failure or unsafe assumption | Required guidance |
|---|---|
| "Calling the factory enables compaction" | False. Supply both token budgets or custom strategies. |
| Only one token budget is supplied | No default compaction strategy is created; validate both values together. |
| `max_output_tokens >= max_context_window_tokens` | Factory raises `ValueError`; test this contract. |
| Default file memory is assumed to be side-effect free | It writes under `{cwd}/agent-file-memory`; set an explicit store or disable it. |
| Python recipe uses `disable_file_access=True` | Invalid for 1.13.0. File access is opt-in by leaving `file_access_store=None`. |
| Web search unexpectedly appears | It is conditionally auto-added for clients implementing `SupportsWebSearchTool`; disable it explicitly when unwanted. |
| Harness run omits `AgentSession` | Default approval middleware raises at runtime. Always create or restore a session. |
| "Always approve" is treated as authorization | It is session UX state. Use AGT and application authorization for enforceable policy. |
| Auto-approval callback matches only a tool name | Name collisions can approve an unintended tool. Match arguments and server boundary where relevant. |
| Shell deny list or confined workdir is called a sandbox | Explicitly false. These are convenience pre-filters; use an actual isolation boundary and AGT policy. |
| File access, shell, background agents, or looping are presented as stable defaults | They are opt-in and experimental or prerelease in the current Python stack. |
| Loop uses `loop_max_iterations=None` | Reject in canonical recipes. Use an explicit positive cap. |
| Headless host enables plan mode or approval-required tools without a caller UX | Requests can stall. Disable the feature or implement the protocol interaction. |
| External skill source is trusted implicitly | Skill content and scripts are untrusted input; validate source and integrity. |
| Background agent is trusted because it is "internal" | It can exfiltrate input or inject output. Vet identity, tools, and returned content. |
| Restored session crosses tenant or user boundaries | Treat session IDs as untrusted and authorize before load. |
| Hosting package version is used to infer service lifecycle | Track adapter package and Hosted Agents service status independently. |
| Harness security guidance is treated as an eval framework | Link to evaluation skills; do not absorb general eval ownership. |

---

## 10. Upstream pin and reference policy

### Verified baseline on 2026-08-05

| Upstream | Verified value | Pin policy |
|---|---|---|
| `agent-framework` | `1.13.0` stable | Record for user-facing release context; do not use the meta-package in canonical hosted dependencies |
| `agent-framework-core` | `1.13.0` stable | `~=1.13.0` |
| Python release tag | `python-1.13.0` at `e39a8a2e79c8c8987a0b9082d3ccb8665734b897` | Record SHA in audit notes and source links |
| `agent-framework-foundry` | `1.10.4` stable | `~=1.10.4` when the Foundry recipe is installed |
| `agent-framework-foundry-hosting` | `1.0.0b260730` prerelease | Exact `==1.0.0b260730` |
| `agent-framework-tools` | `1.0.0b260730` prerelease | Exact pin only for shell references |

Authoritative sources:

- [Agent Harness documentation](https://learn.microsoft.com/agent-framework/agents/harness)
- [`create_harness_agent` signature at Python 1.13.0](https://github.com/microsoft/agent-framework/blob/e39a8a2e79c8c8987a0b9082d3ccb8665734b897/python/packages/core/agent_framework/_harness/_agent.pyi)
- [Factory implementation at Python 1.13.0](https://github.com/microsoft/agent-framework/blob/e39a8a2e79c8c8987a0b9082d3ccb8665734b897/python/packages/core/agent_framework/_harness/_agent.py)
- [Loop implementation and default cap](https://github.com/microsoft/agent-framework/blob/e39a8a2e79c8c8987a0b9082d3ccb8665734b897/python/packages/core/agent_framework/_harness/_loop.py)
- [Official plan/execute sample](https://github.com/microsoft/agent-framework/blob/e39a8a2e79c8c8987a0b9082d3ccb8665734b897/python/samples/02-agents/harness/harness_research.py)
- [Foundry hosting adapter guidance](https://learn.microsoft.com/azure/foundry/how-to/develop/framework-hosted-agents)
- [Agent session persistence guidance](https://learn.microsoft.com/agent-framework/agents/conversations/storage#persisting-sessions-across-restarts)
- [PyPI: agent-framework](https://pypi.org/project/agent-framework/)
- [PyPI: agent-framework-foundry-hosting](https://pypi.org/project/agent-framework-foundry-hosting/)

The future `references/upstream-pin.md` must:

- use freshness tier B;
- use `automation_tier: auto`;
- set `validation.runnable: true`;
- require only `pypi` and `github_only`;
- track the stable core, Foundry provider, exact hosting prerelease, and exact
  tools prerelease when shell coverage is present;
- poll the official Harness, hosting, and session-storage documentation;
- include known issues for experimental file access, background agents,
  looping, and prerelease shell tooling;
- validate the published signature, not only imports;
- re-check web-search and approval defaults on every minor refresh;
- re-check service lifecycle independently of hosting-package semver.

### Reference-file single source of truth

The future skill should create:

| File | Responsibility |
|---|---|
| `skills/agent-framework-harness/SKILL.md` | Decision guidance, architecture, maturity matrix, boundaries, security, and imperative links |
| `skills/agent-framework-harness/references/python/local_harness.py` | Canonical local construction and session use |
| `skills/agent-framework-harness/references/python/hosted_harness.py` | Canonical `ResponsesHostServer` wiring |
| `skills/agent-framework-harness/references/python/plan_execute.py` | Explicit host approval boundary and bounded execute loop |
| `skills/agent-framework-harness/references/python/session_recovery.py` | Opaque session serialize/restore shape |
| `skills/agent-framework-harness/references/python/test_harness_contract.py` | Offline contract smoke |
| `skills/agent-framework-harness/references/upstream-pin.md` | Machine-readable version, source, known-issue, and validation contract |

Each Python reference must carry the validator-required
`../../SKILL.md § <Section Title>` header and compile cleanly. `SKILL.md` must
not paste the same function or class bodies inline.

---

## 11. Future offline smoke-test design

The first deterministic smoke must verify signature, defaults, feature
classification, and agent construction without credentials, network access, or
a live model call.

### Test mechanism

1. Install the exact/compatible pins from `upstream-pin.md`.
2. Define a minimal `BaseChatClient` test double whose response method is never
   called during construction.
3. Change the working directory to a temporary directory so default file
   memory cannot write into the repository.
4. Use `inspect.signature(create_harness_agent)` to assert the public contract.
5. Construct agents and inspect providers, middleware, tools, options, and
   compaction strategy.
6. Import `ResponsesHostServer` and compile the hosted reference, but do not
   call `server.run()` and do not invoke the agent.

### Required assertions

- return annotation and constructed object are `Agent`;
- `disable_todo`, `disable_mode`, `disable_file_memory`,
  `disable_web_search`, and `disable_tool_auto_approval` default to `False`;
- `file_access_store`, `skills_provider`, `skills_paths`,
  `background_agents`, `shell_executor`, and `loop_should_continue` default to
  `None`;
- `loop_max_iterations` resolves to 10 in the pinned release;
- a bare factory call includes history, todo, mode, and file memory;
- a bare factory call excludes compaction, shared file access, skills,
  background agents, shell, and loop middleware;
- a bare factory call includes `ToolApprovalMiddleware` and
  `MessageInjectionMiddleware`;
- default approval middleware has no caller-supplied heuristic callbacks;
- both token-budget values add before-call and after-call compaction;
- one missing token-budget value does not create the default strategy;
- custom before-only and after-only strategies activate only their requested
  phases;
- `disable_compaction=True` overrides custom strategies;
- file access appears only when `file_access_store` is supplied;
- skills appear only when a provider or path is supplied;
- explicit looping adds `AgentLoopMiddleware` with the explicit positive cap;
- `default_options={"store": False}` survives factory option merging;
- `max_output_tokens` sets `max_tokens` only when the caller did not already
  provide it;
- invalid token budgets raise the documented `ValueError`;
- no construction path calls a model or Azure endpoint.

The smoke prints stable markers for pin validation, including:

```text
HARNESS_SIGNATURE_OK
HARNESS_DEFAULTS_OK
HARNESS_COMPACTION_OK
HARNESS_CONSTRUCTION_OK
HOSTING_IMPORT_OK
```

This offline smoke is T1/T2 evidence, not a waiver of the catalog's Azure test
policy. Because the final skill includes an executable Foundry Hosted recipe,
its implementation PR must also add a registered T3 fixture or obtain an
explicit maintainer-approved exception before merge. The offline smoke remains
valuable because it isolates upstream signature and construction drift from
model availability, quota, RBAC, and hosting transients.

---

## 12. Future catalog integration

Implementation of this design must be a separate change and include:

1. the new skill and references listed above;
2. a 200-1024 character frontmatter description with explicit `USE FOR` and
   `DO NOT USE FOR` ownership boundaries;
3. `metadata.version: "1.0.0"`;
4. an entry in `.github/skill-deps.yml`, depending on
   `foundry-hosted-agents` for the hosted adapter boundary and using forward
   fanout deliberately;
5. the offline smoke and the required Azure test decision from section 11;
6. cross-links from the three adjacent skills only where their routing tables
   would otherwise misroute Harness questions;
7. the `scripts/build-site.py` category entry, README catalog entry, plugin
   MINOR version bump, matching marketplace version, generated docs, and
   AGENTS.md catalog counts;
8. `[skill-rewrite]` and, if adjacent skill bodies change, `[multi-skill]`
   commit tags;
9. T0, pin validation, import smoke, reference compilation, and all required
   live evidence.

The implementation must not expand into a general Agent Framework guide. It
should remain the canonical contract for this one factory and its immediate
runtime composition.

---

## 13. Acceptance criteria

The future skill is ready only when:

- a reader can choose correctly among Harness, Hosted Agents, AGT, Foundry
  Skills, and eval ownership in under one minute;
- every factory default matches the pinned published Python signature and
  implementation;
- compaction is never described as active without token budgets or custom
  strategies;
- web-search and approval behavior use the conditional/default wording in
  section 3;
- every autonomous recipe has an explicit positive `loop_max_iterations`;
- native approval is explicitly described as UX, not governance;
- shell confinement and deny lists are explicitly described as non-sandboxing;
- experimental and prerelease surfaces are visibly labeled;
- local, hosted, plan/execute, and recovery references each have one canonical
  source file;
- Hosted Agents service lifecycle and hosting-package lifecycle are tracked
  independently;
- the offline smoke proves signature/defaults/construction without a model
  call;
- the implementation PR satisfies the catalog's separate Azure evidence rule;
- no deployment, RBAC, Foundry Skills REST, AGT policy, or general eval content
  leaks into this skill's ownership.

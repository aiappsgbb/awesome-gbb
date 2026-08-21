---
name: agent-framework-harness
description: >
  Build Microsoft Agent Framework Python agents with create_harness_agent: plan/execute modes, persistent todos, context compaction, session/file memory, approval UX, recovery, and opt-in file access, skills, background agents, shell, and bounded looping. Covers actual defaults, internal provider/middleware ordering, local construction, and ResponsesHostServer wiring for Foundry Hosted Agents. USE FOR: Agent Harness, create_harness_agent, harness defaults, plan mode, execute mode, TodoProvider, FileMemoryProvider, compaction, tool approval, auto_approval_rules, AgentSession recovery, loop_should_continue, shell_executor, background_agents, ResponsesHostServer harness wiring. DO NOT USE FOR: deployment, RBAC, containers, or lifecycle (use foundry-hosted-agents); deterministic policy, audit, authorization, or sandbox governance (use foundry-agt); Foundry Skills REST distribution (use foundry-skill-catalog); general eval design (use foundry-evals).
metadata:
  version: "1.0.0"
---

## Quick decision table

| Need | Owner |
|---|---|
| Compose a Microsoft Agent Framework `Agent` with Harness providers, middleware, modes, todos, compaction, recovery, approval UX, or opt-in executors | `agent-framework-harness` |
| Deploy, authorize, containerize, roll out, or operate a hosted agent | [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) |
| Enforce deterministic authorization, policy, audit, or governance | [`foundry-agt`](../foundry-agt/SKILL.md) |
| Publish or consume centrally distributed skills through Foundry Skills REST | [`foundry-skill-catalog`](../foundry-skill-catalog/SKILL.md) |
| Design evaluations or scoring | [`foundry-evals`](../foundry-evals/SKILL.md) |

Agent Harness is runtime scaffolding, not hosting. Native approval provides interactive UX and session-backed standing-rule convenience; it is not non-bypassable policy. `ResponsesHostServer` adapts an existing `Agent` and does not create the Harness composition.

This skill excludes deployment, RBAC, identity grants, containers, registries, `azure.yaml`, rollout, service lifecycle, deterministic governance, audit ownership, sandbox ownership, Foundry Skills REST distribution, and general evaluation design.

## Architecture and internal factory pipeline

`create_harness_agent` returns a normal Agent Framework `Agent` around any compatible chat client. Preserve this exact context-provider order:

1. history;
2. optional after-call `CompactionProvider`;
3. todo;
4. `AgentModeProvider`;
5. `FileMemoryProvider`;
6. optional `FileAccessProvider`;
7. optional `SkillsProvider`;
8. optional `BackgroundAgentsProvider`;
9. optional shell provider;
10. caller context providers.

Before-call compaction is not a context provider: it is attached to `agent.compaction_strategy`. When both token budgets create the shared strategy, the factory assembles the before-call strategy and after-call `CompactionProvider` phases together.

Preserve this tool order:

1. conditional web-search tool when the client implements `SupportsWebSearchTool` and web search is not disabled;
2. optional shell tool when `shell_executor` is supplied and the client implements `SupportsShellTool`;
3. caller-supplied tools.

Preserve this middleware order, outermost first:

1. optional `AgentLoopMiddleware`;
2. default `ToolApprovalMiddleware`;
3. always-on `MessageInjectionMiddleware`;
4. caller middleware.

Python 1.14.0 accepts either one caller middleware object or a sequence through
the `middleware` parameter; both forms remain appended after the built-ins.

The default history provider is `InMemoryHistoryProvider`. Per-service-call history persistence and provider-owned state are session-backed, but neither is durable across process loss unless the host persists the full `AgentSession`. Pending tool approval stops autonomous progress and returns control to the caller. The loop is outermost, so each iteration is a complete run through history, providers, approval, and telemetry.

## Default, opt-in, and experimental feature matrix

| Feature | Pinned factory behavior | Maturity and use |
|---|---|---|
| Function invocation | Always wired by the returned `Agent`. | Released. |
| Per-service-call history | Always enabled with default `InMemoryHistoryProvider`; not durable without full session persistence. | Released; persist the opaque `AgentSession` for restart recovery. |
| Todo | Default-on unless `disable_todo=True`. | Released. |
| Plan/execute mode | Default-on, initially `plan`, unless `disable_mode=True`. | Released; disable in headless hosts unless their protocol supports approval and mode transitions. |
| File memory | Default-on unless `disable_file_memory=True`; the default store is `{cwd}/agent-file-memory`. | Released; choose an explicit store and tenant boundary or disable it. |
| Compaction | Supported but inactive unless both token budgets are supplied; custom phases can activate independently. | Released; never claim a bare factory compacts. |
| Web search | `disable_web_search=False` by default, but the tool is added only when the client implements `SupportsWebSearchTool`; otherwise the factory warns. | Released; disable for deterministic/offline runs and reverify capability detection on refresh. |
| Approval middleware | Default-on unless `disable_tool_auto_approval=True`; coordinates queued approvals and session-backed standing rules. | Released interactive UX only; requires `AgentSession`, not a deterministic authorization boundary. |
| Auto-approval callbacks | No callbacks unless `auto_approval_rules` is supplied. | Opt-in; inspect arguments whenever risk is argument-dependent. |
| Message injection | Always-on; no-op when its session queue is empty. | Released. |
| OpenTelemetry | Factory sets the OTel provider name. | Released; telemetry destination and sensitive-data settings remain caller-owned. |
| Shared file access | Opt in only through `file_access_store`; Python 1.14.0 has no `disable_file_access` parameter. | Experimental; read and write tools require approval by default, and the host owns access policy and real sandboxing. |
| Skills | Opt-in through `skills_provider` and/or `skills_paths`. | Released; external skills are untrusted input and are not Foundry Skills REST distribution. |
| Background agents | Opt-in through `background_agents`; child sessions and running tasks are process memory, not restart state. | Experimental; Python 1.14.0 adds bounded `BackgroundAgentsProvider.release_session(...)`, which long-lived hosts must call when evicting a session. |
| Shell | Requires `shell_executor` and a client implementing `SupportsShellTool`. | Experimental and prerelease. |
| Autonomous looping | Opt-in through `loop_should_continue`; the default cap resolves to `10`. | Experimental; every recipe must pass an explicit positive cap. |
| Caller providers and middleware | Opt-in advanced extension surfaces. | Preserve the built-in order. |

### Compaction activation

Supplying both `max_context_window_tokens` and `max_output_tokens` creates one shared default `ContextWindowCompactionStrategy`. The before-call phase is assigned to `agent.compaction_strategy`; the after-call phase is installed through `CompactionProvider`. A custom before-only strategy can independently populate `agent.compaction_strategy`, and a custom after-only strategy can independently add `CompactionProvider`. `disable_compaction=True` overrides default and custom strategies. Supplying only one token budget does not create the shared default strategy.

Released Python 1.14.0 still invokes after-run providers on every
`AgentLoopMiddleware` iteration. Upstream issue
[#7236](https://github.com/microsoft/agent-framework/issues/7236) is fixed on
`main` but not in 1.14.0. Keep explicit loop caps and revalidate after-run
compaction when the next stable core release lands.

## Canonical local Python recipe

> **MUST:** Copy or adapt [`references/python/local_harness.py`](references/python/local_harness.py). Do not reproduce its functions inline.

Keep both token budgets so compaction is active, the explicit `.agent-memory` store, disabled web search, and the `AgentSession` passed to `agent.run`. Any compatible chat client can replace `FoundryChatClient`. Foundry constructs an async `AIProjectClient`, so use an async Azure credential and close it through an async context manager or an equivalent host-owned lifecycle.

## Canonical Foundry Hosted recipe

> **MUST:** Copy or adapt [`references/python/hosted_harness.py`](references/python/hosted_harness.py), then use [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) for deployment, RBAC, containers, rollout, and lifecycle. Do not reproduce the reference functions inline.

Keep `default_options={"store": False}` because the hosting adapter owns Responses transcript history. The pinned `ResponsesHostServer` uses the Agent Server Responses 2.x provider-backed session, checkpoint, and function-approval storage model and still rejects a history provider that loads messages. Therefore the Harness must receive the reference's no-load/no-store `InMemoryHistoryProvider` (`load_messages=False`, `store_inputs=False`, and `store_outputs=False`). `FoundryChatClient` constructs an async `AIProjectClient`, so use an async Azure credential. The reference's internally created `DefaultAzureCredential` is process-lifetime and its handle is not exposed. A host requiring deterministic close must create and inject its own async credential, retain that handle, and close it.

The baseline also disables mode, file memory, and web search. Re-enable mode only when the protocol transports explicit plan approval and transitions. Re-enable file memory only after choosing durable storage, authenticated tenant partitioning, and path policy.

| Surface | Status |
|---|---|
| Harness factory stable core | `agent-framework-core` 1.14.x stable. |
| Python hosting adapter | `agent-framework-foundry-hosting==1.0.0b260813`, exact prerelease pin. |
| Hosted Agents service | Separate lifecycle: the current [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) contract treats container deployment as GA and source-code deployment as preview. |

Do not infer service maturity from adapter semver or adapter maturity from service status.

## Safe plan-to-execute pattern

> **MUST:** Use [`references/python/plan_execute.py`](references/python/plan_execute.py). Do not collapse it into one agent or reproduce its functions and classes inline.

Use separate plan and execute agents because the default `mode_set` tool is model-accessible and auto-approved. The planning agent must expose neither `mode_set` nor looping, so it cannot switch itself into execution. Share the history provider, todo provider, file-memory store, and full session to preserve state continuity.

The host callback is the plan-approval boundary: persist the session, display the plan, obtain explicit caller approval, and only then set execute mode. The execute agent alone receives an execute-scoped loop with an explicit positive cap. Never use `loop_max_iterations=None`.

Inspect the structured response before reading `.text`. A `function_approval_request` must return caller control as the full `AgentResponse`, as represented by `ToolApprovalRequired`; reducing it to `.text` discards the pending approval.

## Session persistence and recovery

> **MUST:** Copy or adapt [`references/python/session_recovery.py`](references/python/session_recovery.py). Do not reproduce its helper bodies inline.

Persist and restore the full opaque `AgentSession`, not only transcript text. Restore it with the same agent, providers, middleware, and stores. Partition durable state by authenticated tenant and user; authorize the session identifier before loading; reject caller-supplied serialized state; and never mutate provider-owned keys directly.

Full `AgentSession` persistence restores serializable session, provider, and middleware state, including history, approval, mode, and todo state. It does not serialize provider-instance runtime or external stores. `BackgroundAgentsProvider` child sessions and running `asyncio` tasks are non-serializable process memory; after restart, running tasks are **LOST**. Python 1.14.0 resolves issue [#7385](https://github.com/microsoft/agent-framework/issues/7385) with `await provider.release_session(session)`, whose default cancellation path is bounded to 30 seconds. Long-lived hosts must invoke that API when a session is evicted.

File-memory and other external stores must be made separately durable and partitioned by authenticated tenant and user. Assign one owner to transcript persistence: in the hosted recipe, keep `store=False` and the no-load/no-store Harness history provider so the adapter remains the owner.

## Offline contract and pin validation

> **MUST:** Run [`references/python/test_harness_contract.py`](references/python/test_harness_contract.py) with the packages and validation procedure in [`references/upstream-pin.md`](references/upstream-pin.md). Do not reproduce the smoke-test bodies inline.

The smoke validates construction, signature, defaults, provider and middleware order, compaction phases, hosted imports, and plan/execute composition without credentials, network access, or a model call. Import-only success is insufficient.

## Harness vs Hosted Agents vs AGT

| Concern | Agent Framework Harness | Foundry Hosted Agents | Agent Governance Toolkit |
|---|---|---|---|
| Primary job | Compose an agentic runtime around a chat client | Host, scale, identify, deploy, and expose an agent | Enforce deterministic action policy and produce governance evidence |
| Main object | `Agent` returned by `create_harness_agent` | Container/runtime plus Responses or Invocations endpoint | Middleware or sidecar policy enforcement |
| Plan, todos, compaction, memory | Owned | Not supplied by hosting itself | Not owned |
| Tool approval | Session-backed UX prompts and standing approvals | Transports approval content; no policy semantics by itself | Deterministic allow, deny, sanitize, escalate, and audit |
| Looping | Optional Harness middleware | Runs whatever the hosted Agent implements | Can gate actions inside a loop but does not create the loop |
| Shell | Optional executor and environment provider | Supplies compute boundary only when configured | Owns policy/sandbox governance, not shell convenience |
| Persistence | `AgentSession`, history provider, file memory | Hosted session and conversation lifecycle | Audit and policy state |
| HTTP/Responses | No. | Owns it through the adapter and platform. | No. |
| Deployment and RBAC | Excluded | Owned by `foundry-hosted-agents` | Excluded |
| Audit/policy/governance | No. | Platform operations only. | Owns configured policy surfaces and evidence. |
| Security boundary | No | Hosting isolation is a separate platform concern | Yes for the policy surfaces explicitly configured |

```text
Harness Agent -> AGT middleware/policy -> ResponsesHostServer
              -> Foundry hosted runtime, identity, scale, and lifecycle
```

## Failure modes and security callouts

| Symptom | Cause | Fix |
|---|---|---|
| Compaction was expected but does not run. | One or both token budgets are absent, and no relevant custom strategy was supplied. | Supply both budgets for the shared default, or explicitly configure the required custom phase. |
| Construction raises `ValueError` for token budgets. | `max_output_tokens >= max_context_window_tokens`, or a budget is not positive. | Validate positive budgets and require `max_output_tokens < max_context_window_tokens`. |
| A run writes files beneath an unexpected working directory. | Default file memory writes to `{cwd}/agent-file-memory`. | Set an explicit tenant-partitioned store or use `disable_file_memory=True`. |
| Construction rejects `disable_file_access=True` as an invalid argument. | Python 1.14.0 has no `disable_file_access` parameter. | Leave `file_access_store=None` to keep shared file access disabled. |
| Planning switches into execution before host approval. | One agent exposed the model-accessible, auto-approved `mode_set` tool while planning. | Use separate plan/execute agents; disable mode and looping on the planning agent. |
| A loop is unbounded or runs during planning. | `loop_max_iterations=None` or a predicate not restricted to execute mode was used. | Use an explicit positive cap and an execute-only predicate. |
| Approval appears to wait inside a loop, or the host sees empty text. | Autonomous code continued after a pending request, or reduced the structured response to `.text`. | Stop the loop, return the complete response through `ToolApprovalRequired`, and resume only after host interaction. |
| Default approval middleware fails at runtime. | `AgentSession` was omitted from the Harness run. | Create or restore an `AgentSession` and pass it to `agent.run`. |
| A standing auto-approval rule approves an unintended tool. | Its callback matched only a tool name that collides across tools or servers. | Match arguments and the server boundary as well as the tool name. |
| A standing or "always approve" choice is treated as authorization. | Standing approval is session-backed UX state, not an enforceable authorization boundary. | Implement authorization in the application and use [`foundry-agt`](../foundry-agt/SKILL.md) for enforceable policy. |
| A headless run stalls on a plan or tool request. | Plan mode or approval-required tools were enabled without caller UX. | Disable those features or implement the complete plan/approval protocol. |
| Serializable session state disappears after restart. | The default in-memory history or only message text was persisted. | Persist and restore the full opaque `AgentSession` with the same composition; separately persist and partition external stores. |
| Background work was expected to resume after restart. | `BackgroundAgentsProvider` child sessions and running `asyncio` tasks are non-serializable process memory. | Treat running tasks as LOST after restart; call `await provider.release_session(session)` on eviction and use a durable queue for restartable work. |
| A restored session crosses a tenant or user boundary. | Session identifiers and serialized payloads were trusted before tenant/user authorization, or durable state was not partitioned. | Authorize the authenticated tenant and user before loading, partition state by both boundaries, and reject untrusted session payloads. |
| Hosted transcripts duplicate or history is rejected. | `store=False` is missing, or the Harness history provider loads/stores transcript messages while `ResponsesHostServer` owns them. | Keep `default_options={"store": False}` and use the no-load/no-store history provider from the hosted reference. |
| Hosting adapter semver is used to infer the Hosted Agents service lifecycle. | Adapter package maturity and Hosted Agents service status were treated as one lifecycle. | Track and report the adapter lifecycle and Hosted Agents service lifecycle independently. |
| Web search is assumed present but no tool appears. | The client does not implement `SupportsWebSearchTool`; the false disable flag alone cannot add support. | Check client capability, heed the warning, and reverify on every MINOR refresh. |
| Web search appears unexpectedly. | A compatible client plus `disable_web_search=False` causes the factory to add the tool automatically. | Set `disable_web_search=True` when search is unwanted and reverify capability detection on refresh. |
| An external skill source is trusted. | It can supply untrusted instructions or scripts. | Validate source and integrity, and constrain execution. |
| A background agent is trusted. | It can exfiltrate input or inject output. | Vet identity, tools, returned content, and cancellation. |
| Shell, background agents, or shared file access are treated as stable defaults. | Opt-in experimental/prerelease surfaces were misclassified. | Label them explicitly, check current upstream issues, and require host controls. |
| A shell deny list or confined working directory is called a sandbox. | Convenience prefilters were mistaken for an isolation boundary. | Use real process or container isolation plus governance policy; keep deny lists and workdir confinement only as convenience prefilters. |
| Custom composition changes behavior unexpectedly. | Caller providers or middleware were inserted ahead of built-ins or reordered. | Append caller extensions after the documented built-in pipeline and validate order offline. |
| Harness security guidance is treated as a general evaluation framework. | Runtime security callouts were mistaken for evaluation ownership. | Route general evaluation design and scoring to [`foundry-evals`](../foundry-evals/SKILL.md) or the applicable evaluation skill. |

**Security boundaries — do not weaken these statements:**

- Deny lists and a constrained working directory are not a sandbox.
- File access and file memory require tenant partitioning and host-owned path policy.
- Background agents multiply credentials, tools, cost, and cancellation obligations.
- Loop caps bound iterations and cost; they do not establish safety.
- Native approval is bypassable by host design and is not deterministic authorization.
- Deterministic governance belongs to [`foundry-agt`](../foundry-agt/SKILL.md).

## Upstream pin and reference policy

- Record `agent-framework` 1.14.0 for release context, but the `agent-framework` meta-package MUST NOT be used in canonical hosted dependency sets; canonical hosted dependencies use component packages.
- Use compatible stable pins for `agent-framework-core~=1.14.0`, `agent-framework-foundry~=1.11.0`, and `azure-identity~=1.25.3`.
- Pin `agent-framework-foundry-hosting==1.0.0b260813`, its Agent Server beta dependencies, and optional `agent-framework-tools==1.0.0b260730` exactly because they are prerelease surfaces.
- Preserve the immutable audited source evidence: tag `python-1.14.0` at SHA `ae7fa3389c8f70b3ed702b0e04b85a3ee62b1bd1`.
- Track the Hosted Agents service lifecycle separately from the Python hosting adapter lifecycle.
- On every MINOR refresh, reverify web-search capability detection and empty approval-rule behavior.
- Before using experimental file access, background agents, looping, or shell, inspect the open issues recorded in [`references/upstream-pin.md`](references/upstream-pin.md).
- Validate signatures, resolved defaults, construction, and provider/middleware ordering; an import-only check is not sufficient.
- Keep non-trivial Python code single-sourced under `references/python/`; `SKILL.md` provides imperative links and must not duplicate canonical bodies.

## Completion checklist

- [ ] One-minute routing distinguishes Harness, Hosted Agents, AGT, Skills REST, and eval ownership.
- [ ] Exact pinned defaults and provider/middleware order are verified.
- [ ] Compaction is described as conditional on both budgets or explicit custom phases.
- [ ] Web search is described as conditional on client capability.
- [ ] Every autonomous recipe uses an explicit positive loop cap.
- [ ] Native approval is identified as UX rather than authorization or governance.
- [ ] Deny lists and working-directory confinement are identified as non-sandbox controls.
- [ ] Experimental and prerelease features are visibly labeled.
- [ ] All canonical local, hosted, plan/execute, recovery, and offline files are linked without duplicated bodies.
- [ ] Hosting adapter and Hosted Agents service statuses remain separate.
- [ ] Offline smoke proves signature, defaults, construction, and ordering without a model call.
- [ ] Azure T3 evidence is registered or a maintainer-approved exception is documented.
- [ ] No deployment, RBAC, lifecycle, Skills REST, AGT policy, or general eval ownership leaks into this skill.

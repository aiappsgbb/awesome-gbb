---
name: foundry-mcp-aca-jobs
description: >
  Build job-backed MCP servers for Foundry when the control plane must stay
  responsive and the real work belongs in an ACA Job. USE FOR: MCP Tasks,
  SEP-2663, ACA Jobs, long-running/asynchronous MCP tools, callbacks,
  external job orchestration, durable task state, secure job handoff.
  DO NOT USE FOR: general MCP hosting or producer-side server deployment
  (use foundry-mcp-aca), business logic that should run directly in the MCP
  server or a Docket container, or arbitrary provisioning patterns.
metadata:
  version: "1.0.0"
---

> **ACA Job-backed companion to [`foundry-mcp-aca`](../foundry-mcp-aca/SKILL.md).**
> The MCP server owns protocol and state; the ACA Job owns execution.

See [foundry-mcp-aca](../foundry-mcp-aca/SKILL.md) for producer-side MCP
hosting.

For the job-backed companion itself, see
[foundry-mcp-aca-jobs](../foundry-mcp-aca-jobs/SKILL.md).

## When to use

- A request can run longer than a normal tool call and needs durable progress.
- The client may or may not advertise MCP Tasks, so the server needs a
  compatibility path.
- You want the control plane to stay responsive while the job does the work.
- The result should be stored externally and surfaced as a stable URL, not
  streamed inline as a large payload.
- The worker must run in a separate ACA Job, not inside the MCP server process.

Use [`foundry-mcp-aca`](../foundry-mcp-aca/SKILL.md) for producer-side MCP
hosting. Use [`azd-patterns`](../azd-patterns/SKILL.md) for the canonical ACA
Job module and digest-convergence pattern.

## Architecture and shared-image contract

This skill uses one immutable image and two runtime roles:

1. the **FastMCP control plane** serves the API, Tasks adapter, callbacks, and
   lifecycle reconciliation;
2. the **ACA Job worker** runs the business handler and writes the result; and
3. both roles are built from the same image digest, but launched with different
   commands and different user-assigned managed identities.

The canonical runtime split is:

| Role | Entry point | Identity | Responsibility |
|---|---|---|---|
| MCP app | `python -m app.mcp_server` | app UAMI | protocol, policy, callbacks, durable task state |
| ACA Job | `python -m app.job_worker` | job UAMI | execution, output persistence, callback delivery |

The image is built once from `templates/Dockerfile`, then converged in postdeploy
so the app and job both point to the same digest. Never let the app and job drift
onto separate images, commands, or identities.

## Protocol contract (Tasks + Compatibility tools)

The server must support both protocol shapes:

- **Tasks-aware clients** use the `io.modelcontextprotocol/tasks` extension and
  receive durable task objects.
- **Tasks-unaware clients** use the explicit tools:
  - `start_aca_job`
  - `get_aca_job_status`
  - `cancel_aca_job`

Tasks-aware requests are wired through `AcaTasksExtension`. Compatibility-tool
calls go straight to the orchestrator. The server evaluates Tasks support on each
request; it never assumes a previous request's capability still applies.

The start contract is fixed:

```text
start_aca_job(jobType, idempotencyKey, inputRef, callbackAlias)
```

- `jobType` and `callbackAlias` are allowlisted by policy.
- `inputRef` must be an https URL on an allowlisted host.
- callers never provide raw ARM IDs, image tags, commands, secrets, or callback URLs.
- polling is authoritative; notifications are optional.
- the worker uses the official `CONTAINER_APP_JOB_EXECUTION_NAME` environment
  variable to bind each job execution back to the control record.

## Control record and lifecycle

The control record is the source of truth. It carries:

`taskId`, `ownerScope`, `jobType`, `idempotencyKeyHash`, `requestFingerprint`,
`inputRef`, `callbackAlias`, `lifecycleState`, `acaExecutionId`, `resultUrl`,
`errorCode`, `callbackDeliveryState`, `callbackErrorCode`,
`cancellationRequestedAt`, `startAttemptedAt`, `startAttemptCount`,
`workerClaimedAt`, `workerClaimToken`, `workerClaimExpiresAt`, `createdAt`,
`updatedAt`, `completedAt`, and `_etag`.

Lifecycle mapping:

| Control record state | MCP `status` | Public result |
|---|---|---|
| `Accepted` / `Starting` / `Running` | `working` | poll again |
| `Succeeded` + `resultUrl` present | `completed` | `isError: false`, `structuredContent.status = Succeeded` |
| `Succeeded` + `resultUrl` missing | `failed` | `RESULT_REFERENCE_MISSING` |
| `Failed` | `completed` | `isError: true`, `content` carries the stable error code |
| `Cancelled` | `cancelled` | no result payload |

A successful business run is therefore a `completed` task with `isError: false`.
A business failure is also `completed`, but with `isError: true`.

## Idempotency and uncertain-start reconciliation

The start flow is:

1. derive a deterministic `taskId` from the owner scope, job type, and idempotency
   key hash;
2. persist the new record with a request fingerprint;
3. claim the record with an ETag; and
4. start the ACA Job with the exact job policy digest and command contract.

If the same `taskId` arrives again with the same request fingerprint, the existing
record is returned. If the fingerprint changes, the store raises
`IDEMPOTENCY_KEY_REUSED`.

Uncertain starts are reconciled deterministically:

- `Accepted`/`Starting` tasks are re-checked until the ACA execution appears.
- If multiple executions match, the worker selects a winner by status priority,
  start time, and execution ID, then best-effort stops the losers.
- If the start never becomes observable, the task stays `Starting` until the
  reconciliation budget expires.
- After three attempts or five minutes, the start path fails with
  `START_RECONCILIATION_EXHAUSTED`.

The store itself uses optimistic concurrency (`_etag`) and rejects stale claims.
Cosmos failures map to `CONTROL_STORE_UNAVAILABLE`.

## Callback contract

Callbacks are minimal and fixed:

```json
{"taskId":"...","acaExecutionId":"...","status":"Succeeded","resultUrl":"https://..."}
```

The callback payload never carries the business result body. The worker writes the
result to blob storage first, then sends only the URL.

Callback auth modes are explicit:

- `managed_identity` sends a bearer token for the configured audience.
- `key_vault` sends `X-Callback-Key` using the named secret.

The callback route only trusts the configured callback principal. If an existing
callback blob already exists with different bytes, the server raises
`CALLBACK_PAYLOAD_CONFLICT`; identical payloads are idempotent.
Delivery retries are bounded and may end in `CALLBACK_DELIVERY_EXHAUSTED` or
`CALLBACK_DELIVERY_REJECTED`.

## Security and least-privilege RBAC

Trust the ACA Easy Auth header path only when `MCP_ACA_JOBS_AUTH_MODE` is exactly
`aca-easy-auth`.

Allowlists are policy-driven, not caller-driven:

- `jobType`
- `callbackAlias`
- `inputHosts`
- `resultHosts`
- optional `allowed_owner_scopes`

The app and job use separate UAMIs, even though they share the same image digest.
That separation is intentional: one identity reads and updates the control plane;
the other executes the job and writes output.

Do not accept caller-supplied image references, commands, environment overrides,
ARM IDs, secrets, large result bodies, or callback URLs.

## Deploy with azd

The deployment contract is copy-verbatim `azd`:

- `templates/azure.yaml` wires one service and one postdeploy chain.
- `templates/infra/main.bicep` composes the app, job, Cosmos control store,
  identities, and role assignments.
- `templates/infra/scripts/converge_image.py` resolves the immutable digest and
  updates both runtime resources to the same image.
- `templates/infra/scripts/verify_deployment.py` proves the live resources still
  match the documented contract.

Copy the entire `templates/` tree into a project, keep the shared digest pattern,
and let `azd up` or `azd deploy` run the converged postdeploy flow. Do not fork the
module shapes here; use the canonical ACA Job module from `azd-patterns`.

## Operate and observe

Runtime behavior is observable and bounded:

- `MCP_ACA_JOBS_RECONCILE_INTERVAL_SECONDS` controls background reconciliation.
- `MCP_ACA_JOBS_LEASE_MINUTES` controls the worker lease.
- `MCP_ACA_JOBS_POLICY_JSON` carries the allowlist policy.
- `CONTAINER_APP_JOB_EXECUTION_NAME` binds the worker to a specific ACA execution.

Telemetry only emits safe fields:

`task.id`, `job.type`, `task.state`, `aca.execution.id`, `operation`, `outcome`,
`error.code`, and `azure.request.id`.

The worker persists output before callback delivery, so a callback outage does not
erase the result. The server's `/health` route stays light; operational visibility
comes from task status, result URLs, and telemetry.

## Stable errors

These codes are user-visible and must stay stable within the `1.x` contract:

| Code | Meaning |
|---|---|
| `CONTROL_STORE_UNAVAILABLE` | Cosmos or other store failure |
| `IDEMPOTENCY_KEY_REUSED` | same task ID, different request fingerprint |
| `INVALID_JOB_TYPE` / `INVALID_CALLBACK_ALIAS` | allowlist rejection |
| `INVALID_INPUT_REFERENCE` / `INVALID_RESULT_REFERENCE` | bad URL shape or host |
| `TASK_FORBIDDEN` | caller not authorized for the record |
| `ARM_STATUS_UNAVAILABLE` | transient or unreadable ACA execution state |
| `ARM_START_REJECTED` / `ARM_STOP_REJECTED` | ACA rejected the control-plane call |
| `DEPLOYMENT_CONTRACT_MISMATCH` | app/job digest, command, or container contract drift |
| `START_RECONCILIATION_EXHAUSTED` | uncertain start could not be resolved |
| `RESULT_REFERENCE_MISSING` | succeeded task never produced a durable result URL |
| `WORKER_EXECUTION_FAILED` | worker handler crashed |
| `CALLBACK_PAYLOAD_CONFLICT` | callback body changed for the same blob path |
| `CALLBACK_DELIVERY_REJECTED` / `CALLBACK_DELIVERY_EXHAUSTED` | callback transport failed |

`Failed` tasks are surfaced as `completed` with `isError: true`. `Succeeded` tasks
are surfaced as `completed` with `isError: false`.

## Test implementation

The implementation is pinned to contract tests, not hand-wavy prose:

- `scripts/tests/test_foundry_mcp_aca_jobs_template.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_protocol.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_azure.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_callbacks.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_store.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_orchestrator.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_worker.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_models.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_telemetry.py`

Those tests assert the section map, dependency parity, shared-image convergence,
separate identities, callback payload shape, allowlist behavior, stable error
mapping, and the absence of Docket-style execution in the worker path.

The upstream pin's validation script installs the pinned package set, imports the
canonical modules, verifies the Tasks extension and ACA job methods, and prints
three success markers. Keep the pin in sync with this contract before shipping.

## Non-goals

- general MCP hosting or producer-side server deployment
- running business logic directly in the MCP server process
- Docket-based execution or any other alternate job runtime
- caller-supplied image digests, commands, env vars, secrets, or callback URLs
- large inline result payloads or opaque callback bodies
- hand-rolled provisioning that bypasses `azd`
- sharing one UAMI between the app and the job

## Related skills

| Skill | When to use it |
|---|---|
| [`foundry-mcp-aca`](../foundry-mcp-aca/SKILL.md) | producer-side MCP server hosting |
| [`azd-patterns`](../azd-patterns/SKILL.md) | canonical ACA Job Bicep and digest convergence |
| [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) | hosted agents that consume MCP tools |
| [`foundry-prompt-agents`](../foundry-prompt-agents/SKILL.md) | prompt-only Foundry agents without a worker |
| [`foundry-observability`](../foundry-observability/SKILL.md) | telemetry and log/trace wiring |

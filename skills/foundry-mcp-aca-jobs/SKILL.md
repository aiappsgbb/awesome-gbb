---
name: foundry-mcp-aca-jobs
description: >
  Build job-backed MCP servers for Foundry when the control plane must stay
  responsive and execution belongs in ACA Jobs. USE FOR: MCP Tasks, SEP-2663,
  ACA Jobs, durable result claims, callbacks, external job orchestration, and
  shared-image worker handoff. DO NOT USE FOR: producer-side MCP hosting (use
  foundry-mcp-aca), Service Bus/queue/event-dispatch workflows, or business
  logic that should run directly in the MCP server or Docket container.
metadata:
  version: "1.2.0"
---

> **ACA Job-backed companion to [foundry-mcp-aca](../foundry-mcp-aca/SKILL.md).**
> The MCP server owns protocol and state; the ACA Job owns execution.

For the companion itself, see [foundry-mcp-aca-jobs](../foundry-mcp-aca-jobs/SKILL.md).

# Foundry MCP ACA Jobs

Copy verbatim from the canonical files below. Do **not** duplicate code bodies
inline here.

| Canonical file | Contract |
|---|---|
| [references/python/app/__init__.py](references/python/app/__init__.py) | Package exports and canonical imports |
| [references/python/app/aca_jobs.py](references/python/app/aca_jobs.py) | ACA job adapter and control-plane client |
| [references/python/app/aca_tasks_extension.py](references/python/app/aca_tasks_extension.py) | Tasks extension adapter boundary |
| [references/python/app/callbacks.py](references/python/app/callbacks.py) | Callback transport and payload writer |
| [references/python/app/control_store.py](references/python/app/control_store.py) | Durable control-store contract |
| [references/python/app/job_worker.py](references/python/app/job_worker.py) | ACA Job worker entrypoint |
| [references/python/app/mcp_server.py](references/python/app/mcp_server.py) | FastMCP server assembly |
| [references/python/app/models.py](references/python/app/models.py) | Control-record models and lifecycle mapping |
| [references/python/app/orchestrator.py](references/python/app/orchestrator.py) | Start, reconcile, and cancel orchestration |
| [references/python/app/telemetry.py](references/python/app/telemetry.py) | Safe telemetry wiring |
| [templates/Dockerfile](templates/Dockerfile) | Shared runtime image |
| [templates/pyproject.toml](templates/pyproject.toml) | Runtime dependency lock contract |
| [templates/azure.yaml](templates/azure.yaml) | `azd` service wiring and postdeploy flow |
| [templates/infra/main.bicep](templates/infra/main.bicep) | Main deployment composition |
| [templates/infra/app.bicep](templates/infra/app.bicep) | MCP app module |
| [templates/infra/cosmos.bicep](templates/infra/cosmos.bicep) | Durable control-store module |
| [templates/infra/identity-rbac.bicep](templates/infra/identity-rbac.bicep) | Least-privilege identity/RBAC module |
| [templates/infra/scripts/converge_image.py](templates/infra/scripts/converge_image.py) | Digest convergence helper |
| [templates/infra/scripts/verify_deployment.py](templates/infra/scripts/verify_deployment.py) | Deployment verification helper |
| [../azd-patterns/references/bicep/aca-job.bicep](../azd-patterns/references/bicep/aca-job.bicep) | Canonical ACA Job module |

## When to use this skill

- A request can run longer than a normal tool call and needs durable progress.
- The client may or may not advertise MCP Tasks, so the server needs a
  compatibility path.
- You want the control plane to stay responsive while the job does the work.
- The result should be stored externally and surfaced as a stable URL, not
  streamed inline as a large payload.
- The worker must run in a separate ACA Job, not inside the MCP server process.

Use [foundry-mcp-aca](../foundry-mcp-aca/SKILL.md) for producer-side MCP
hosting. Use [azd-patterns](../azd-patterns/SKILL.md) for the canonical ACA
Job module and digest-convergence pattern.

## Architecture and shared-image contract

This skill uses one immutable image and two runtime roles:

1. the **FastMCP control plane** serves the API, Tasks adapter, callbacks, and
   lifecycle reconciliation;
2. the **ACA Job worker** runs the business handler and writes the result; and
3. both roles are built from the same image digest, but launched with different
   commands and different user-assigned managed identities.

| Role | Entry point | Identity | Responsibility |
|---|---|---|---|
| MCP app | `python -m app.mcp_server` | app UAMI | protocol, policy, callbacks, durable task state |
| ACA Job | `python -m app.job_worker` | job UAMI | execution, output persistence, callback delivery |

The image is built once from `templates/Dockerfile`, then converged in
postdeploy so the app and job both point to the same digest. Never let the app
and job drift onto separate images, commands, or identities.

## Protocol contract

The server supports two contract paths:

- the **standards-first MCP Tasks path** for clients that advertise the Tasks
  extension; and
- the **compatibility tools** path for clients that do not.

Both paths share the same control record, callback, and durable-result contract.
Do not model this skill as Service Bus, queues, topics, subscriptions, or any
event-dispatch fanout pattern.

### Standards-first MCP Tasks path

Prefer the public MCP Tasks result-claim path whenever the client supports it.
`AcaTasksExtension` binds the `io.modelcontextprotocol/tasks` extension to the
durable control record, worker claim, and callback flow.

KI-001 releases only when the first-class server result-claim API is public:
validation must import `TasksExtension` from `fastmcp_tasks`, `inspect` its
`lifespan` source, confirm `docket_lifespan` is present there, and confirm the
`AcaTasksExtension` source/lifespan does not contain that Docket path.

### Compatibility tools

For clients without MCP Tasks, expose the explicit tools:

- `start_aca_job(jobType, idempotencyKey, inputRef, callbackAlias)`
- `get_aca_job_status(taskId)`
- `cancel_aca_job(taskId)`

These tools are a compatibility path, not a second workflow model. They still
write the same control record and still persist results through the same worker.

## Control record and lifecycle

The control record is the source of truth. It carries `taskId`, `ownerScope`,
`jobType`, `idempotencyKeyHash`, `requestFingerprint`, `inputRef`,
`callbackAlias`, `lifecycleState`, `acaExecutionId`, `resultUrl`, `errorCode`,
`callbackDeliveryState`, `callbackErrorCode`, `cancellationRequestedAt`,
`startAttemptedAt`, `startAttemptCount`, `workerClaimedAt`, `workerClaimToken`,
`workerClaimExpiresAt`, `createdAt`, `updatedAt`, `completedAt`, and `_etag`.

| Control record state | MCP `status` | Public result |
|---|---|---|
| `Accepted` / `Starting` / `Running` | `working` | poll again |
| `Succeeded` + `resultUrl` present | `completed` | `isError: false`, `structuredContent.status = Succeeded` |
| `Failed` + business error | `completed` | `isError: true`, `content` carries the stable error code |
| `Failed` + `RESULT_REFERENCE_MISSING` | `completed` | `isError: true`, `content` carries `RESULT_REFERENCE_MISSING` |
| `Cancelled` | `cancelled` | no result payload |

`RESULT_REFERENCE_MISSING` is an internal failed terminal state. It is never a
protocol-level `failed` response; the MCP projection stays `completed` with
`isError: true`.

## Idempotency and uncertain-start reconciliation

The start flow is:

1. derive a deterministic `taskId` from the owner scope, job type, and
   idempotency-key hash;
2. persist the new record with a request fingerprint;
3. claim the record with an ETag; and
4. start the ACA Job with the exact job policy digest and command contract.

If the same `taskId` arrives again with the same request fingerprint, return
the existing record. If the fingerprint changes, the store raises
`IDEMPOTENCY_KEY_REUSED`.

Uncertain starts are reconciled deterministically:

- `Accepted`/`Starting` tasks are re-checked until the ACA execution appears.
- If multiple executions match, the worker selects a winner by status priority,
  start time, and execution ID, then best-effort stops the losers.
- If the start never becomes observable, the task stays `Starting` until the
  reconciliation budget expires.
- After three attempts or five minutes, the start path fails with
  `START_RECONCILIATION_EXHAUSTED`.

The store itself uses optimistic concurrency (`_etag`) and rejects stale
claims. Cosmos failures map to `CONTROL_STORE_UNAVAILABLE`.

## Callback contract

Callbacks are minimal and fixed:

```json
{"taskId":"...","acaExecutionId":"...","status":"Succeeded","resultUrl":"https://..."}
```

The callback payload never carries the business result body. The worker writes
the result to blob storage first, then sends only the URL.

Callback auth modes are explicit:

- `managed_identity` sends a bearer token for the configured audience.
- `key_vault` sends `X-Callback-Key` using the named secret.

The callback route only trusts the configured callback principal. If an
existing callback blob already exists with different bytes, the server raises
`CALLBACK_PAYLOAD_CONFLICT`; identical payloads are idempotent. Delivery
retries are bounded and may end in `CALLBACK_DELIVERY_EXHAUSTED` or
`CALLBACK_DELIVERY_REJECTED`.

## Security and least-privilege RBAC

Trust the ACA Easy Auth header path only when `MCP_ACA_JOBS_AUTH_MODE` is
exactly `aca-easy-auth`.

Allowlists are policy-driven, not caller-driven:

- `jobType`
- `callbackAlias`
- `inputHosts`
- `resultHosts`
- optional `allowed_owner_scopes`

The app and job use separate UAMIs, even though they share the same image
digest. That separation is intentional: one identity reads and updates the
control plane; the other executes the job and writes output.

Do not accept caller-supplied image references, commands, environment
overrides, ARM IDs, secrets, large result bodies, callback URLs, or event
dispatch hooks.

## Deploy with azd

The deployment contract is `azd` only. Copy the canonical files verbatim; do
not fork the template shapes here.

- `templates/azure.yaml`
- `templates/infra/main.bicep`
- `templates/infra/app.bicep`
- `templates/infra/cosmos.bicep`
- `templates/infra/identity-rbac.bicep`
- `templates/infra/scripts/converge_image.py`
- `templates/infra/scripts/verify_deployment.py`
- `templates/pyproject.toml`
- `templates/Dockerfile`
- `../azd-patterns/references/bicep/aca-job.bicep`

Use `azd up` or `azd deploy` to run the converged postdeploy flow. Do not hand
roll `az` deploy sequences or reimplement the digest convergence logic here.

For a brownfield platform, keep `resourceGroupName` as the child resource group
that receives the app, Job, and UAMIs, and set `platformResourceGroupName` to
the resource group containing the existing ACR, Container Apps environment,
storage account, and optional Cosmos account. The template scopes those
existing resources explicitly across resource groups while preserving the
single-resource-group default. The named output and callback blob containers
are created in the existing storage account; they are not pre-existing
containers.

## Operate and observe

Runtime behavior is bounded and observable:

- `MCP_ACA_JOBS_RECONCILE_INTERVAL_SECONDS`
- `MCP_ACA_JOBS_LEASE_MINUTES`
- `MCP_ACA_JOBS_POLICY_JSON`
- `CONTAINER_APP_JOB_EXECUTION_NAME`

Telemetry only emits safe fields:

`task.id`, `job.type`, `task.state`, `aca.execution.id`, `operation`,
`outcome`, `error.code`, and `azure.request.id`.

The worker persists output before callback delivery, so a callback outage does
not erase the result. The server's `/health` route stays light; operational
visibility comes from task status, result URLs, and telemetry.

## Stable errors

These codes are user-visible and must stay stable within the `1.x` contract:

| Family | Stable codes |
|---|---|
| `TASK_*` | `TASK_NOT_FOUND`, `TASK_FORBIDDEN` |
| `INVALID_*` | `INVALID_JOB_TYPE`, `INVALID_CALLBACK_ALIAS`, `INVALID_INPUT_REFERENCE`, `INVALID_RESULT_REFERENCE` |
| `IDEMPOTENCY_*` | `IDEMPOTENCY_KEY_REUSED` |
| `ARM_*` | `ARM_STATUS_UNAVAILABLE`, `ARM_START_REJECTED`, `ARM_STOP_REJECTED` |
| `START_*` | `START_RECONCILIATION_EXHAUSTED` |
| `ACA_EXECUTION_*` | `ACA_EXECUTION_FAILED`, `ACA_EXECUTION_STOPPED`, `ACA_EXECUTION_STATE_UNRESOLVED` |
| `RESULT_*` | `RESULT_REFERENCE_MISSING` |
| `CALLBACK_*` | `CALLBACK_DELIVERY_REJECTED`, `CALLBACK_DELIVERY_EXHAUSTED`, `CALLBACK_PAYLOAD_CONFLICT` |
| `CONTROL_STORE_*` | `CONTROL_STORE_UNAVAILABLE` |
| `DEPLOYMENT_*` | `DEPLOYMENT_CONTRACT_MISMATCH` |
| `WORKER_*` | `WORKER_EXECUTION_FAILED` |

`RESULT_REFERENCE_MISSING` stays in the failed terminal family, but the MCP
projection is still `completed` with `isError: true`.

## Test the implementation

The implementation is pinned to contract tests, not prose:

- `scripts/tests/test_foundry_mcp_aca_jobs_template.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_protocol.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_azure.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_callbacks.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_store.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_orchestrator.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_worker.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_models.py`
- `scripts/tests/test_foundry_mcp_aca_jobs_telemetry.py`

Pin validation must print exactly:

- `ok fastmcp external tasks adapter`
- `ok aca jobs sdk surface`
- `ok foundry-mcp-aca-jobs imports`

## Non-goals

- general MCP hosting or producer-side server deployment
- running business logic directly in the MCP server process
- Docket-based execution or any other alternate job runtime
- Service Bus, queues, topics, subscriptions, or event-dispatch orchestration
- caller-supplied image digests, commands, environment overrides, secrets, or
  callback URLs
- large inline result payloads or opaque callback bodies
- hand-rolled provisioning that bypasses `azd`
- sharing one UAMI between the app and the job

## Related skills

| Skill | When to use it |
|---|---|
| [foundry-mcp-aca](../foundry-mcp-aca/SKILL.md) | producer-side MCP server hosting |
| [azd-patterns](../azd-patterns/SKILL.md) | canonical ACA Job Bicep and digest convergence |
| [foundry-prompt-agents](../foundry-prompt-agents/SKILL.md) | prompt-agent fallback when tool work needs durable job-backed execution or callbacks |
| [foundry-hosted-agents](../foundry-hosted-agents/SKILL.md) | hosted agents that consume MCP tools |
| [foundry-observability](../foundry-observability/SKILL.md) | telemetry and log/trace wiring |

# Foundry MCP ACA Jobs - Design Specification

- **Date:** 2026-09-02
- **Status:** Approved
- **New skill:** `foundry-mcp-aca-jobs`
- **Initial skill version:** `1.0.0`
- **Related skills:** `foundry-mcp-aca`, `azd-patterns`,
  `foundry-prompt-agents`, and `foundry-hosted-agents`
- **Scope of this document:** Design only. Implementation is a later change.

---

## 1. Decision

Create a producer-side skill for exposing a standards-compliant remote MCP
server on Azure Container Apps (ACA). The server starts and manages executions
of pre-provisioned ACA Jobs. The business workload runs only in ACA Jobs; the
MCP server is a control-plane adapter and never executes the business workload
in-process.

The standards-first path implements the MCP Tasks extension
`io.modelcontextprotocol/tasks` (SEP-2663). A task-aware `tools/call` starts an
ACA Job and returns a durable task handle. `tasks/get` translates the persisted
control state and the ACA execution state. `tasks/cancel` requests that the
specific ACA execution stop.

Clients that do not advertise MCP Tasks use three ordinary, non-blocking MCP
tools:

- `start_aca_job`
- `get_aca_job_status`
- `cancel_aca_job`

Both paths use the same orchestration service and Cosmos DB control record.
Neither path holds an MCP request open until the business job finishes.

The MCP server Container App and the ACA Job use **one OCI image by default**.
The image contains both Python modules, but Bicep configures different commands:

```text
MCP Container App: python -m app.mcp_server
ACA Job:           python -m app.job_worker
```

The deployment builds and pushes this image once, resolves its immutable digest,
and configures both resources with the exact same
`registry/repository@sha256:...` reference. The resources retain separate
managed identities, environment configuration, and secret access.

---

## 2. Goals and success criteria

### Goals

1. Give MCP producers a reusable Python/FastMCP, azd, Bicep, and managed
   identity pattern for durable ACA Job-backed tools.
2. Map MCP Tasks directly to an external ACA Job lifecycle without using
   FastMCP/Docket to execute the business workload.
3. Preserve compatibility with MCP clients that do not yet advertise the Tasks
   extension.
4. Make duplicate submissions safe through a mandatory idempotency key, Cosmos
   optimistic concurrency, and job-side idempotency by `taskId`.
5. Restrict callers to allowlisted job types and callback aliases. Callers never
   supply an ARM resource ID, image, command, environment override, secret, or
   callback URL.
6. Keep large inputs and outputs in job-owned storage. MCP and callback payloads
   carry references only.
7. Prove the design with unit tests, in-process MCP protocol tests, a live Azure
   fixture, and endpoint smokes from both a Foundry Prompt Agent and a Foundry
   Hosted Agent.
8. Extend `azd-patterns` with the canonical ACA Job Bicep module instead of
   duplicating that module in the new skill.

### Success criteria

The implementation is complete only when:

- a task-aware client receives a durable MCP task handle and can poll it to a
  standards-compliant terminal result;
- an unaware client can start, inspect, and cancel the same work through the
  fallback tools without a long-held request;
- the control record survives MCP server restarts and concurrent requests;
- duplicate submissions with the same idempotency key return the same task;
- an uncertain ARM start is reconciled without creating duplicate business
  effects;
- the MCP app and ACA Job run the exact same immutable image digest using their
  distinct configured commands;
- callbacks resolve only approved aliases and contain no business payload;
- the MCP app identity can start, read, and stop only the configured ACA Job
  resources; and
- live Azure evidence is included in the implementation pull request as
  required by `AGENTS.md`.

---

## 3. Non-goals

- MCP Tasks is a protocol adapter, not the business execution runtime.
- No FastMCP/Docket worker runs the business workload.
- No arbitrary job provisioning or image selection per tool call.
- No Service Bus, queue, or event-driven dispatch architecture.
- No large input or result transport through MCP responses or callbacks.
- No arbitrary callback URLs.
- No caller-supplied ARM resource IDs, job names, commands, environment
  variables, or execution templates.
- No separate default image for the MCP server and job worker.
- No claim that current Foundry clients advertise MCP Tasks until a live probe
  proves it. Their required compatibility contract is the fallback tool set.
- No implementation changes in this design-only commit.

---

## 4. Architecture

```text
                                   control plane
 MCP client / Foundry agent       (short requests only)
          |
          | HTTPS /mcp
          v
 +----------------------------+
 | MCP Server Container App   |
 | python -m app.mcp_server   |
 |                            |
 | - FastMCP transport/auth   |
 | - MCP Tasks adapter        |
 | - fallback MCP tools       |
 | - allowlist validation     |
 | - ARM execution adapter    |
 | - reconciliation loop      |
 +-------------+--------------+
               |
       +-------+-----------------------+
       |                               |
       | Cosmos control records        | ARM start/read/stop
       v                               v
 +----------------------+      +---------------------------+
 | Cosmos DB            |      | Pre-provisioned ACA Job   |
 | durable task state   |      | python -m app.job_worker  |
 +----------+-----------+      +-------------+-------------+
            ^                                |
            | ETag updates                   | job-owned I/O
            |                                v
            |                       +----------------------+
            |                       | Blob/data services   |
            |                       | input/output refs    |
            |                       +----------+-----------+
            |                                  |
            +----------------------------------+
                         result URL/state

 ACA Job -- allowlisted callback alias --> approved webhook target
```

### Shared-image invariant

One source tree and one Dockerfile produce one image containing:

- `app.mcp_server`, the HTTP/MCP process;
- `app.job_worker`, the ACA Job process; and
- shared models, validation, telemetry, and storage helpers.

The image does not rely on a default command to choose its role. The Container
App and Job definitions each set an explicit command. The MCP process must not
import or invoke the business worker entrypoint as a dispatch mechanism. The
worker may share pure libraries with the server, but its business handler is
reachable only through the Job command.

The shipped template has one image parameter and no separate server-image or
worker-image override. Consumers can fork the template outside the skill
contract, but the documented and tested path is always one digest for both
resources.

The azd deployment follows the established `azd-patterns` service-plus-job
shape:

1. azd builds and pushes the image once;
2. the deployment resolves the pushed image digest;
3. the final Bicep convergence step configures both the Container App and Job
   with that digest; and
4. deployment verification reads both Azure resource templates and fails if
   either uses a tag, a different digest, or the wrong command.

The implementation may use the catalog's existing `azd deploy` plus
`postdeploy` convergence-hook pattern, but it must not introduce a second image
build for the Job.

---

## 5. Component and file design

The implementation will add the following package. Names below are the intended
single sources of truth, not duplicate snippets in `SKILL.md`.

| File | Responsibility |
|---|---|
| `skills/foundry-mcp-aca-jobs/SKILL.md` | Consumer contract, decision guidance, deployment flow, protocol behavior, security rules, failure modes, and cross-references; version `1.4.2`. |
| `skills/foundry-mcp-aca-jobs/references/python/app/mcp_server.py` | Canonical FastMCP server assembly and HTTP entrypoint. |
| `skills/foundry-mcp-aca-jobs/references/python/app/aca_tasks_extension.py` | Small MCP Tasks `ServerExtension` adapter when the pinned FastMCP Tasks extension cannot bind directly to external ACA execution state. |
| `skills/foundry-mcp-aca-jobs/references/python/app/orchestrator.py` | Shared start, get, cancel, idempotency, status translation, and reconciliation service used by Tasks and fallback tools. |
| `skills/foundry-mcp-aca-jobs/references/python/app/control_store.py` | Cosmos point reads, creates, ETag-guarded state transitions, idempotency lookup, and forward-compatible document filtering. |
| `skills/foundry-mcp-aca-jobs/references/python/app/aca_jobs.py` | Narrow adapter around the documented ACA Job start, execution-list/read, and stop operations. |
| `skills/foundry-mcp-aca-jobs/references/python/app/job_worker.py` | Example ACA Job entrypoint that loads the control record, renews an exact-token worker lease while the handler runs, enforces idempotency by `taskId`, writes job-owned output, persists the result reference, and sends the allowlisted callback. |
| `skills/foundry-mcp-aca-jobs/references/python/app/models.py` | Typed request, response, control-record, lifecycle, and stable-error models shared by both entrypoints. |
| `skills/foundry-mcp-aca-jobs/references/python/app/callbacks.py` | Callback alias resolution, managed-identity or Key Vault authentication, bounded retries, and payload construction. |
| `skills/foundry-mcp-aca-jobs/templates/pyproject.toml` | Bounded dependency pins for FastMCP, MCP Tasks support, Azure identity, App Containers management, Cosmos, storage, HTTP, and telemetry packages. |
| `skills/foundry-mcp-aca-jobs/templates/Dockerfile` | One production image containing both entrypoints; no embedded secrets. |
| `skills/foundry-mcp-aca-jobs/templates/azure.yaml` | azd service and hook wiring for a single build and digest convergence. |
| `skills/foundry-mcp-aca-jobs/templates/infra/main.bicep` | Composition root for the MCP app, conditionally applied resource-group tags, shared image digest, Cosmos resources, identities, RBAC, and the canonical ACA Job module from `azd-patterns`. |
| `skills/foundry-mcp-aca-jobs/references/upstream-pin.md` | Machine-readable bounded upstream pins, validation script, expected output, known issues, and audit trail. |
| `skills/foundry-mcp-aca-jobs/test-fixture/consumer_prompt.md` | Live Copilot CLI Azure fixture. |
| `skills/foundry-mcp-aca-jobs/tests/` | Unit and in-process MCP tests that import the canonical reference modules rather than redefining them. |
| `skills/azd-patterns/references/bicep/aca-job.bicep` | New canonical ACA Job module, including explicit command and immutable image-digest inputs. |

`SKILL.md` links imperatively to the canonical Python files and the shared Bicep
module. It must not paste their non-trivial bodies inline. Reference-file
headers must point to real `SKILL.md` section headings as required by
`AGENTS.md`.

The built-in FastMCP Tasks extension currently describes Docket-backed execution
of a Python tool body. That is not the execution model here. During
implementation, the pinned FastMCP version must be probed for a supported seam
that maps task protocol methods to external state without scheduling the tool
body. If it does not provide that seam, `aca_tasks_extension.py` implements the
small public `ServerExtension` adapter. Under no outcome may Docket execute
`job_worker.py` or the business handler.

---

## 6. Protocol contracts

### 6.1 One start tool, two negotiated result paths

`tools/list` exposes `start_aca_job`, `get_aca_job_status`, and
`cancel_aca_job`.

`start_aca_job` accepts only:

| Argument | Contract |
|---|---|
| `jobType` | Required allowlist key. Server configuration maps it to one pre-provisioned Job resource and worker policy. |
| `idempotencyKey` | Required caller-generated key. Uniqueness is scoped to the authenticated caller and `jobType`. |
| `inputRef` | Required job-owned data reference. Inline business payloads and credential-bearing URLs are rejected. |
| `callbackAlias` | Required allowlist key resolved to server-controlled callback configuration. |

If the request advertises `io.modelcontextprotocol/tasks`, the server may return
the standard Tasks `CreateTaskResult` with `resultType: "task"`. The task record
must already be durable before the response is sent, as required by SEP-2663.

If the request does not advertise the extension, the server must not return a
task result. It returns a normal tool result immediately after making one ARM
start attempt:

```json
{
  "taskId": "opaque-server-generated-id",
  "jobType": "allowlisted-type",
  "status": "Starting",
  "acaExecutionId": null,
  "pollAfterMs": 2000
}
```

`acaExecutionId` is nullable only when the ARM start outcome is uncertain. A
definitive ARM rejection returns an error instead of a success-shaped result.
The value becomes available through polling after reconciliation.

### 6.2 MCP Tasks methods

The adapter implements the Tasks extension contract rather than inventing
parallel methods:

- `tasks/get` reads the control record, refreshes a non-terminal execution from
  Azure when needed, and returns the standard MCP task shape.
- `tasks/cancel` records cancellation intent with an ETag-guarded update, asks
  Azure to stop the bound execution, and acknowledges the request. Cancellation
  remains cooperative and eventually consistent, as SEP-2663 requires.
- `tasks/update` is implemented because it belongs to the extension, but v1
  never puts an ACA execution into `input_required`. A valid task with no
  outstanding input requests receives the standards-compliant acknowledgement;
  an unknown task receives the protocol-defined error behavior.

The implementation must use the pinned MCP/FastMCP types and verify the exact
wire shapes in tests. This design deliberately does not reproduce SDK method
signatures.

### 6.3 Compatibility tools

`get_aca_job_status(taskId)` returns:

```json
{
  "taskId": "opaque-server-generated-id",
  "jobType": "allowlisted-type",
  "status": "Running",
  "acaExecutionId": "execution-name",
  "resultUrl": null,
  "errorCode": null,
  "createdAt": "ISO-8601 timestamp",
  "updatedAt": "ISO-8601 timestamp"
}
```

`cancel_aca_job(taskId)` resolves the Job and execution from the control record;
it never accepts either identifier from the caller. It returns immediately with
the task ID, current lifecycle state, and `cancellationRequested: true`.

If cancellation arrives before an execution ID is bound, the intent blocks any
new start attempt. A task that has not reached ARM becomes `Cancelled`; an
uncertain start is reconciled only far enough to find and stop any matching
execution. If ARM start is already in flight, ETag-safe binding preserves the
cancellation intent and cooperatively stops the execution immediately after its
ID becomes durable.

The fallback tools and Tasks methods call the same orchestrator. Their
authorization, idempotency, status mapping, cancellation, and error semantics
must not drift.

---

## 7. Azure API and RBAC mapping

The server uses the documented Azure Container Apps management operations:

| Capability | Azure operation | Custom-role action |
|---|---|---|
| Validate configured Job | Read Job | `Microsoft.App/jobs/read` |
| Start execution | Jobs - Start | `Microsoft.App/jobs/start/action` |
| Read one bound execution | Job Execution - Get | `Microsoft.App/jobs/execution/read` |
| List executions for uncertain-start reconciliation | Jobs Executions - List | `Microsoft.App/jobs/executions/read` |
| Cancel one execution | Jobs - Stop Execution | `Microsoft.App/jobs/stop/execution/action` |

The implementation must verify these provider-operation strings against the
live `Microsoft.App` provider metadata before committing the role definition.
It must not add `Microsoft.App/jobs/write`, delete, arbitrary resource-group
Contributor, or stop-multiple-executions permissions.

The custom role definition can be assignable at the deployment resource-group
or subscription boundary required by Azure, but each role assignment is scoped
to a specific allowlisted Job resource. Multiple job types produce multiple
job-scoped assignments.

Azure RBAC authorizes the start operation but cannot constrain the execution
template body. The server must therefore construct the full body from trusted
configuration, verify the expected digest and command before submission, and
run under a dedicated identity that no caller can use directly.

### Identity separation

| Identity | Required access |
|---|---|
| MCP app UAMI | Custom start/read/stop role on allowlisted Jobs; Cosmos data-plane access to control records; ACR pull for the shared image. |
| ACA Job UAMI | Cosmos data-plane access to its control record; job-owned input/output data access; callback-target invocation or Key Vault secret read; ACR pull for the same shared image. |

The two runtime identities are separate by default even though the image is
shared. The Job identity does not receive Job start/stop permissions. The MCP
identity does not receive business-data access unless a documented status
projection requires it.

The MCP endpoint authentication and remote HTTP transport follow
`foundry-mcp-aca`; this new skill cross-references that contract rather than
forking it.

---

## 8. Control-record data model

Cosmos DB is the durable source of truth for task identity, idempotency,
authorization scope, result reference, and reconciliation metadata. Azure
remains the source of truth for the physical Job execution state.

The control container partitions by `ownerScope`, an opaque hash derived from
the authenticated caller. A unique-key policy covers `idempotencyKeyHash`
within that logical partition. The hash is computed over `jobType` and the
caller-provided key; the raw key is not stored.

| Field | Purpose |
|---|---|
| `id` / `taskId` | Opaque server-generated MCP task identifier. |
| `ownerScope` | Opaque authorization and Cosmos partition scope derived from caller identity. |
| `jobType` | Allowlist key used to resolve the target Job and worker policy. |
| `idempotencyKeyHash` | Non-reversible representation of the mandatory idempotency key, scoped with `jobType`. |
| `requestFingerprint` | Hash of canonical `jobType`, `inputRef`, and `callbackAlias`; detects reuse of one key for a different request. |
| `inputRef` | Job-owned input reference; never inline content or a credential-bearing URL. |
| `acaExecutionId` | Bound ACA execution name after start confirmation or reconciliation. |
| `callbackAlias` | Allowlist key only; no callback URL. |
| `lifecycleState` | `Accepted`, `Starting`, `Running`, `Succeeded`, `Failed`, or `Cancelled`. |
| `resultUrl` | Job-owned result reference without embedded credentials. |
| `errorCode` | Stable public error code or null. Raw Azure error bodies remain in protected telemetry only. |
| `callbackDeliveryState` | `NotStarted`, `Pending`, `Delivered`, or `Exhausted`; independent of business lifecycle. |
| `callbackErrorCode` | Delivery-specific stable warning code or null; it does not convert successful business work to `Failed`. |
| `cancellationRequestedAt` | Timestamp or null; cancellation intent does not create an extra lifecycle state. |
| `startAttemptedAt` / `startAttemptCount` | Uncertain-start reconciliation bounds. |
| `workerClaimedAt` / `workerClaimToken` / `workerClaimExpiresAt` | Job-side idempotency evidence and active-lease boundary. The exact-token ETag heartbeat renews the expiry while a business handler runs. Renewal failures are best-effort and safely logged; the next interval retries, while a persistent outage lets the lease expire naturally. |
| `createdAt` / `updatedAt` / `completedAt` | UTC ISO-8601 lifecycle timestamps. |
| `_etag` | Cosmos optimistic concurrency token used on every mutation. |

Large output never enters this record. `resultUrl` points to output owned and
secured by the Job's data plane.

Cosmos documents are filtered to known `TaskRecord` names and aliases before
validation. Unknown future fields are ignored by `TaskRecord` but preserved
across ETag replacement when they are non-system fields. Replacement excludes
`id` and unknown underscore-prefixed service metadata, then overlays canonical
known fields so clearing a known field cannot resurrect its stale raw value.
Malformed known fields fail closed as `CONTROL_STORE_UNAVAILABLE`.

---

## 9. Lifecycle and state mapping

### 9.1 Internal lifecycle

```text
Accepted -> Starting -> Running -> Succeeded
              |          |-----> Failed
              |          `-----> Cancelled
              |----------------> Failed
              `----------------> Cancelled
```

All transitions are monotonic and ETag-guarded. A terminal record never returns
to a non-terminal state.

| Internal state | Meaning |
|---|---|
| `Accepted` | Control record is durable; no dispatcher owns the ARM start yet. |
| `Starting` | One dispatcher holds the ETag claim and the ARM start is pending, accepted, or uncertain. |
| `Running` | Azure reports `Running`, or the worker has claimed the task. |
| `Succeeded` | Azure reports `Succeeded` and the worker persisted a valid `resultUrl`. |
| `Failed` | Azure or the worker reached an unrecoverable failure with a stable `errorCode`. |
| `Cancelled` | Azure reports `Stopped` after cancellation was requested. |

ACA execution states map as follows:

| ACA execution state | Control-state mapping |
|---|---|
| `Processing` | `Starting` for unclaimed `Accepted`/`Starting` records; preserve `Running` once that state or a worker claim is visible. |
| `Running` | `Running` |
| `Succeeded` | `Succeeded` only after the result reference is available; otherwise remain `Running` until the existing timestamp anchor is at least ten minutes old and no worker lease is active, then `Failed` with `RESULT_REFERENCE_MISSING`. |
| `Failed` | `Failed` with `ACA_EXECUTION_FAILED` unless the worker already persisted a more specific stable code. |
| `Stopped` | `Cancelled` when cancellation was requested; otherwise `Failed` with `ACA_EXECUTION_STOPPED`. |
| `Degraded` | Remain `Running` until the existing timestamp anchor is at least ten minutes old and no worker lease is active, then fail with `ACA_EXECUTION_STATE_UNRESOLVED`. |
| `Unknown` | Remain `Running` until the existing timestamp anchor is at least ten minutes old and no worker lease is active, then fail with `ACA_EXECUTION_STATE_UNRESOLVED`. |

The distinct unresolved-reconciliation budget is anchored at
`startAttemptedAt`, falling back to `updatedAt` for records without a start
timestamp. It applies only to a bound `Degraded`/`Unknown` execution or
`Succeeded` execution without a result. Start-reconciliation exhaustion never
applies to bound tasks. Exhaustion clears worker claim fields only when it
persists the resulting terminal failure. Without `startAttemptedAt`, the first
transition into unresolved `Running` may set `updatedAt`; later identical
unresolved observations are no-op reads that preserve both that anchor and the
Cosmos ETag until the budget is exhausted.

### 9.2 MCP Tasks mapping

MCP Tasks and ACA use different terminal semantics. The adapter follows the MCP
specification:

| Control state | MCP task status/result |
|---|---|
| `Accepted`, `Starting`, `Running` | `working` |
| `Succeeded` | `completed` with the original tool's successful `CallToolResult`, containing status and `resultUrl`. |
| `Cancelled` | `cancelled` |
| `Failed` caused by a business or ACA execution failure | `completed` with the original `CallToolResult` marked `isError: true`; SEP-2663 states that tool error results are still completed tasks. |
| Adapter failure represented by a JSON-RPC execution error | `failed` with the standards-defined error object. |

This distinction prevents the internal `Failed` lifecycle label from producing
a non-compliant MCP `failed` status for ordinary tool/business failures.

---

## 10. Idempotency and uncertain-start reconciliation

### Submission

1. Authenticate the caller and derive `ownerScope`.
2. Validate `jobType`, `inputRef`, and `callbackAlias` against server-owned
   policy.
3. Canonicalize the request and compute its fingerprint and idempotency hash.
4. Create the `Accepted` record. A duplicate unique-key conflict reads the
   existing record:
   - same fingerprint: return the same `taskId` and current state;
   - different fingerprint: reject with `IDEMPOTENCY_KEY_REUSED`.
5. Claim `Accepted -> Starting` with `_etag`. Only the winner calls ARM.
6. Start the allowlisted Job with a server-constructed execution template. The
   only per-run values are opaque `ownerScope` and `taskId` arguments. Caller
   input never controls the image, command, environment, identity, or secret
   references.
7. Persist the returned execution ID and timestamps with `_etag`, then return
   the MCP task or fallback result.

### Why two idempotency layers are mandatory

Cosmos creation and ARM Job start cannot be one distributed transaction. A
timeout can occur after Azure accepted the start but before the server recorded
the execution ID. Retrying the start can therefore create more than one
physical execution.

The worker must treat `taskId` as the business idempotency key:

- it conditionally claims the task record before doing work;
- it passes `taskId` to every downstream side-effect surface that supports an
  idempotency key;
- it writes output under a deterministic task-owned location; and
- duplicate executions exit without repeating committed business effects.

The control-record claim alone cannot make a non-idempotent downstream system
safe after a process crash. `SKILL.md` must state this limitation explicitly.

### Reconciliation

The adapter owns a lightweight control-plane reconciler, not a business worker.
It runs on `tasks/get`, `get_aca_job_status`, and a bounded server-extension
lifespan loop. Multiple MCP app replicas coordinate through Cosmos ETags.

For a `Starting` record whose start outcome is uncertain:

1. list executions only for the allowlisted Job and the recorded attempt
   window;
2. match the opaque `taskId` in the server-controlled execution arguments;
3. re-fetch the current ETag-protected record and treat an existing
   `acaExecutionId` or worker claim as authoritative;
4. when unbound, conditionally bind the selected match before stopping anything;
5. stop only discovered executions whose ID differs from the persisted
   authoritative ID; never replace a bound execution merely because sorting
   favors another match;
6. if no match appears after the consistency grace period, retry the start with
   the same `taskId`; and
7. after the configured attempt and time budget, transition an unbound uncertain
   start to `Failed` with `START_RECONCILIATION_EXHAUSTED`. A bound execution
   remains `Running` when an ARM list is temporarily empty.

If `jobs.start` returns after cancellation reconciliation has already persisted
a terminal record, bind its execution ID only when the terminal record has none,
without changing any other terminal field, then best-effort stop that exact late
orphan. An already-known terminal execution observed during ordinary polling is
authoritative and is never stopped by binding.

No reconciliation path creates a new MCP `taskId` or accepts a caller-provided
execution identifier.

---

## 11. Callback behavior

The ACA Job owns business output and callback delivery.

1. The worker writes large output to job-owned storage.
2. It persists the credential-free `resultUrl` and terminal control state using
   the current Cosmos `_etag` only while the current exact non-null
   `workerClaimToken` still matches its claim. A stale worker that observes a
   takeover records safe claim-lost telemetry, leaves authoritative state
   untouched, and suppresses callback delivery.
3. It resolves `callbackAlias` through static, allowlisted configuration.
4. It posts a minimal callback with bounded exponential backoff and jitter.

The callback payload contains only:

```json
{
  "taskId": "opaque-server-generated-id",
  "acaExecutionId": "execution-name",
  "status": "Succeeded",
  "resultUrl": "https://example.com/results/opaque-task-id"
}
```

It contains no business input, business output, secret, access token, SAS token,
raw Azure error, or arbitrary URL.

Managed identity is the default callback authentication mechanism. If the
target cannot accept managed identity, the worker reads a named secret from Key
Vault at runtime. Secret values never enter the control record, execution
override, callback payload, or logs.

Callback delivery state is separate from business lifecycle. If output and the
Job succeed but callback retries exhaust, the task remains `Succeeded`; the
record sets `callbackDeliveryState: "Exhausted"` and
`callbackErrorCode: "CALLBACK_DELIVERY_EXHAUSTED"` while leaving the business
`errorCode` null. The result remains retrievable through polling. On forced
cancellation, the worker may not receive enough time to send a callback, so
polling is always the authoritative cancellation channel.

---

## 12. Security design

### Input and target allowlists

- `jobType` resolves through configuration to one Job resource, expected image
  digest, allowed worker command, input-reference policy, and runtime limit.
- `callbackAlias` resolves through configuration to one HTTPS origin,
  authentication mode, audience, and Key Vault secret name if required.
- `inputRef` must use an approved scheme and host and must not contain embedded
  credentials. The worker authenticates to the data store with managed
  identity.
- `taskId` is the only execution correlation value accepted by status and
  cancellation tools. ARM identifiers come from the control record.

### Prohibited caller influence

The caller cannot set:

- subscription, resource group, Job resource, or execution ID;
- container image, command, raw process arguments, or environment variables;
- the worker's `ownerScope`/`taskId` execution arguments, which the server
  derives after persisting `inputRef`;
- managed identity or RBAC scope;
- callback URL, headers, token, or secret name; or
- inline large input or output.

### Secret and log hygiene

- No secrets in MCP arguments, Cosmos records, Job execution overrides, callback
  payloads, or structured logs.
- Key Vault secret names may be configured; secret values are resolved only in
  worker memory and redacted from exceptions.
- Idempotency keys are stored as hashes and logged only as short correlation
  hashes.
- Result URLs must be credential-free resource URLs. Consumers authenticate
  separately.
- Raw ARM response bodies are not returned to clients.

### Endpoint and data-plane controls

- Reuse the authenticated remote-MCP perimeter from `foundry-mcp-aca`.
- Authorize `jobType` per caller after authentication; authentication alone is
  not enough.
- Use Cosmos DB data-plane RBAC, not account keys.
- Disable local/key authentication on supported Azure resources.
- Assign identities at the narrowest resource or container scope supported by
  each service.

---

## 13. Error semantics

Public errors and delivery warnings use stable codes and safe messages. Azure
request IDs and detailed exceptions remain in protected telemetry.

| Code | Meaning | Retry guidance |
|---|---|---|
| `INVALID_JOB_TYPE` | `jobType` is absent or not allowlisted. | Do not retry unchanged. |
| `INVALID_CALLBACK_ALIAS` | Callback alias is absent or not allowlisted. | Do not retry unchanged. |
| `INVALID_INPUT_REFERENCE` | Input reference violates scheme, host, size, or credential rules. | Do not retry unchanged. |
| `IDEMPOTENCY_KEY_REUSED` | Same scoped key was used with a different request fingerprint. | Use a new key only for genuinely new work. |
| `TASK_NOT_FOUND` | No task exists in the caller's ownership scope. | Do not retry unless creation is still in progress. |
| `TASK_FORBIDDEN` | Caller is not authorized for the task or `jobType`. | Do not retry without authorization change. |
| `ARM_START_REJECTED` | Azure definitively rejected the start. | Retry only when the protected cause is transient. |
| `START_RECONCILIATION_EXHAUSTED` | Start outcome stayed uncertain beyond the bounded policy. | Operator investigation required. |
| `ARM_STATUS_UNAVAILABLE` | Azure status could not be read within the request budget. | Retry after `pollAfterMs`; do not force a terminal transition. |
| `ARM_STOP_REJECTED` | Azure definitively rejected cancellation. | Poll current state; retry only if transient. |
| `ACA_EXECUTION_FAILED` | ACA reported a failed execution without a more specific worker code. | Inspect protected telemetry and Job logs. |
| `ACA_EXECUTION_STOPPED` | ACA stopped without a recorded cancellation request. | Operator investigation required. |
| `ACA_EXECUTION_STATE_UNRESOLVED` | ACA stayed `Degraded` or `Unknown` beyond the bounded reconciliation policy. | Operator investigation required. |
| `RESULT_REFERENCE_MISSING` | Execution succeeded but no result reference arrived within the reconciliation window. | Operator investigation required. |
| `CALLBACK_DELIVERY_EXHAUSTED` | Delivery warning: business work succeeded but callback retries exhausted. | Poll result and repair callback configuration. |

Validation, authorization, and adapter failures use the current pinned MCP and
FastMCP error types. The implementation must not invent numeric JSON-RPC codes
when the protocol already defines one. The Tasks specification's missing-client-
capability behavior is retained where applicable.

---

## 14. Observability

Every control-plane operation emits structured telemetry correlated by
`taskId`, while omitting raw idempotency keys, inputs, outputs, and secrets.

### Traces

- MCP `tools/call`, `tasks/get`, `tasks/cancel`, and fallback tool spans;
- Cosmos create/read/ETag-conflict spans;
- ACA start/list/read/stop spans with Azure request correlation;
- worker claim, business execution, result persistence, and callback spans; and
- reconciliation attempts and duplicate-execution handling.

### Metrics

- starts accepted, rejected, duplicate-hit, and uncertain;
- tasks by lifecycle state and terminal outcome;
- start-to-running and start-to-terminal latency;
- ETag conflict and reconciliation counts;
- cancellation request-to-terminal latency;
- callback attempts, delivery latency, and exhausted retries; and
- image-digest mismatch detection.

### Logs and alerts

Logs include only `taskId`, `jobType`, lifecycle state, execution name,
operation, duration, stable error code, and safe Azure correlation IDs.
Recommended alerts cover reconciliation exhaustion, execution failure rate,
callback exhaustion, digest mismatch, and sustained tasks in `Starting` or
`Running`.

Application Insights and Log Analytics ingestion are asynchronous. The live
skill fixture treats telemetry lookup as best-effort after deterministic
control-plane assertions, following `AGENTS.md` Pattern 13.

---

## 15. Testing design

### 15.1 Unit tests

Tests use mocks/fakes for Azure and callback boundaries and cover:

- all ACA-to-control and control-to-MCP status mappings;
- MCP's special rule that a tool `isError` result is a `completed` task;
- create, duplicate-hit, and key-reused idempotency cases;
- simultaneous ETag claims and monotonic terminal transitions;
- uncertain-start reconciliation with zero, one, and multiple execution
  matches;
- bounded unresolved-state reconciliation from `startAttemptedAt` (falling back
  to a stable, non-churning `updatedAt`) and protection by a renewed active
  worker lease;
- exact-token, ETag-guarded worker heartbeats, transient and unexpected
  heartbeat-error recovery without data loss, off-loop synchronous handlers,
  and heartbeat cleanup on completion, failure, cancellation, takeover, or a
  terminal task;
- callback alias and input-reference allowlists;
- minimal callback payload construction and secret redaction;
- ARM start, list/read, and stop success, transient, denied, not-found, and
  terminal error translation;
- cancellation races where work succeeds before stop completes; and
- terminal late-start adoption and exact orphan stop without terminal lifecycle
  mutation;
- forward-compatible Cosmos replacement that preserves unknown application
  fields without reviving cleared known fields;
- stale worker success/failure rejection after exact-token takeover, including
  callback suppression; and
- shared-image policy validation that rejects tags or different digests.

### 15.2 In-process MCP tests

Use the pinned MCP/FastMCP client and server types to verify:

1. a request advertising `io.modelcontextprotocol/tasks` can receive a durable
   task result;
2. `tasks/get`, `tasks/update`, and `tasks/cancel` use the official wire shapes;
3. a request without the capability never receives `resultType: "task"`;
4. the fallback start/status/cancel tools return immediately;
5. both protocol paths reach the same orchestrator and persisted task; and
6. server restart/reconstruction does not lose a Cosmos-backed task.

The test suite must not use Docket as the business executor.

### 15.3 Image and entrypoint tests

- Build the OCI image once.
- Start `python -m app.mcp_server` from that image and verify `/health` plus an
  MCP initialization roundtrip.
- Start `python -m app.job_worker` from the same image against controlled test
  dependencies and verify that it claims and completes one task.
- Inspect both process configurations and fail if either relies on a different
  image or implicit command.

### 15.4 Live Azure fixture

The Copilot CLI fixture deploys with azd and:

1. uses a UUID suffix for per-run resources;
2. builds and pushes one image;
3. captures its immutable digest;
4. deploys the MCP Container App and pre-provisioned Job with the same digest
   and distinct explicit commands;
5. reads the active MCP app revision and ACA Job execution template to assert
   both use the captured digest;
6. verifies the MCP app health and transport;
7. uses a task-aware test client to start a short Job and poll `tasks/get` to a
   terminal result with a credential-free `resultUrl`;
8. starts a cancellable execution and verifies eventual cancellation semantics;
9. submits the same idempotency key twice and verifies the same `taskId` and one
   committed business result;
10. receives the allowlisted callback and verifies its exact minimal payload;
11. exercises the fallback tools against a client that omits Tasks capability;
12. invokes the same MCP endpoint from a Foundry Prompt Agent and a Foundry
    Hosted Agent; and
13. performs targeted, best-effort cleanup after all hard assertions.

Official Foundry documentation currently establishes remote MCP tool
connectivity but does not establish `io.modelcontextprotocol/tasks` support.
Therefore the Prompt Agent and Hosted Agent smokes use the fallback tools unless
their live handshake explicitly advertises the Tasks extension. The dedicated
task-aware client remains the normative SEP-2663 proof.

The CI environment needs a standing Cosmos account or an equivalently proven
deployment path. The preferred CI shape is a standing account in the dedicated
CI resource group with a UUID-named per-run database/container and managed-
identity data-plane RBAC. The consumer template still provisions Cosmos by
default; CI uses documented brownfield parameters to stay within the shared
matrix timeout. Missing Cosmos infrastructure is a blocking prerequisite, not a
reason to skip assertions.

The fixture inherits all relevant hardening in `AGENTS.md`, including explicit
Azure auth, preinstalled tooling, deterministic marker-file grading, no
recursive Copilot invocation, change-gated dependencies, bounded retries,
soft-pass telemetry lag, and best-effort teardown.

---

## 16. Rollout and compatibility

### Compatibility contract

- Tasks-aware clients receive protocol-native durable tasks.
- Tasks-unaware clients receive immediate normal tool results and use the
  explicit status/cancel tools.
- The server evaluates Tasks capability per request and never assumes support
  from a previous request.
- Polling is authoritative. Notifications are optional and not required for
  v1.
- The fallback tool names and result fields are stable for the `1.x` skill
  contract.

### Repository integration during implementation

The implementation is one deliberate multi-skill change:

1. add `foundry-mcp-aca-jobs` at `1.0.0`;
2. add the canonical ACA Job module and guidance to `azd-patterns` (MINOR bump;
   from current `1.4.10`, that would be `1.5.0` if no intervening change);
3. add a scope cross-reference from `foundry-mcp-aca` to the new Job-backed
   skill and bump it according to the final user-facing edit;
4. register the new fixture in `.github/skill-deps.yml` with dependencies on
   `foundry-mcp-aca`, `azd-patterns`, `foundry-prompt-agents`, and
   `foundry-hosted-agents`;
5. add the skill to the root catalog and `scripts/build-site.py` category map;
6. bump `plugin.json` and `.github/plugin/marketplace.json` by MINOR and keep
   their versions equal (from current `4.29.6`, that would be `4.30.0` if no
   intervening catalog change);
7. update catalog counts from the actual implementation HEAD;
8. rebuild and commit `docs/`;
9. run T0, pin validation/import smoke, unit and in-process tests, and the live
   T3 fixture; and
10. include live Azure evidence in the pull request.

Because implementation adds a skill body and intentionally edits multiple skill
contracts, its commit message requires `[skill-rewrite] [multi-skill]` under
the repository gate. This design-only commit does not use those implementation
tags.

---

## 17. Risks and mitigations

| Risk | Mitigation |
|---|---|
| FastMCP's built-in Tasks extension assumes Docket execution | Probe the pinned extension seam; otherwise use the small public `ServerExtension` adapter. Never run business work in Docket. |
| Foundry clients do not advertise MCP Tasks | Keep the immediate fallback tool contract and prove it from Prompt and Hosted Agents. |
| ARM start succeeds but the response is lost | Persist first, reconcile by opaque task argument, retry with the same `taskId`, and require worker-side idempotency. |
| Two physical executions are created | ETag dispatcher claim, deterministic reconciliation, duplicate stop, and job-side business idempotency by `taskId`. |
| Cancellation races with completion | Record intent, acknowledge cooperatively, and let the observed terminal Azure state win according to SEP-2663. |
| Shared image drifts between app and job | Build once, deploy immutable digest, validate both Azure templates and commands in CI. |
| Shared code implies shared privilege | Use separate runtime UAMIs and configuration; the same bytes do not imply the same identity or permissions. |
| Job start permission allows an execution-template override | Scope the role to one Job, isolate the app UAMI, and construct/validate the full template from trusted configuration; never pass caller-controlled image, command, or environment values. |
| Caller redirects work or exfiltrates data | Allowlist `jobType`, callback alias, and input hosts; never accept ARM IDs, URLs, images, commands, environment overrides, or secrets. |
| Callback target is unavailable | Bounded retries with jitter; keep polling/result URL authoritative and expose delivery exhaustion separately. |
| Cosmos/ARM state diverges | Monotonic ETag transitions plus request-driven and lifespan reconciliation. |
| Live fixture exceeds CI budget | Reuse standing Cosmos in CI, keep jobs short, use one image build, and retain the catalog's shared matrix timeout/retry controls. |

---

## 18. Primary references

### MCP and FastMCP

- [MCP Tasks overview](https://modelcontextprotocol.io/extensions/tasks/overview)
- [SEP-2663 Tasks specification](https://github.com/modelcontextprotocol/ext-tasks/blob/main/specification/draft/tasks.md)
- [FastMCP background tasks](https://gofastmcp.com/servers/tasks)
- [FastMCP server extensions](https://gofastmcp.com/servers/extensions)

### Azure Container Apps and Cosmos DB

- [Jobs in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/jobs)
- [Managed identities in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity)
- [Jobs - Start REST operation](https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/jobs/start?view=rest-resource-manager-containerapps-2026-01-01)
- [Job Execution - Get REST operation](https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/job-execution/job-execution?view=rest-resource-manager-containerapps-2026-01-01)
- [Jobs Executions - List REST operation](https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/jobs-executions/list?view=rest-resource-manager-containerapps-2026-01-01)
- [Jobs - Stop Execution REST operation](https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/jobs/stop-execution?view=rest-resource-manager-containerapps-2026-01-01)
- [Azure permissions for Compute](https://learn.microsoft.com/en-us/azure/role-based-access-control/permissions/compute#microsoftapp)
- [Cosmos DB transactions and optimistic concurrency control](https://learn.microsoft.com/en-us/azure/cosmos-db/database-transactions-optimistic-concurrency)

### Microsoft Foundry

- [Connect agents to Model Context Protocol servers](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol)
- [Using hosted MCP tools with agents](https://learn.microsoft.com/en-us/agent-framework/agents/tools/hosted-mcp-tools)

Repository-specific deployment, testing, and source-of-truth rules are governed
by `AGENTS.md`, `skills/foundry-mcp-aca/SKILL.md`, and
`skills/azd-patterns/SKILL.md`.

# Foundry MCP ACA Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `foundry-mcp-aca-jobs` producer skill, whose authenticated FastMCP server maps MCP Tasks and immediate fallback tools onto durable Azure Container Apps Job executions.

**Architecture:** One Python package and one immutable OCI image contain two explicit entrypoints: `python -m app.mcp_server` for the ACA service and `python -m app.job_worker` for the ACA Job. A custom FastMCP 4 `ServerExtension` implements SEP-2663 against Cosmos DB and ACA rather than Docket; both protocol paths share one orchestrator, while separate UAMIs preserve least privilege.

**Tech Stack:** Python 3.12, FastMCP 4.0.1, MCP Python SDK 2.1.1, `fastmcp-tasks` 4.0.1 wire models, Azure Container Apps management SDK 5.0.0, Cosmos DB 4.16.4, Azure Identity 1.25.3, Blob Storage 12.30.1, Key Vault Secrets 4.11.2, HTTPX 0.28.1, Azure Monitor OpenTelemetry 1.8.9, unittest, azd, Bicep, Docker/OCI, GitHub Actions.

**Approved spec:** [`docs/superpowers/specs/2026-09-02-foundry-mcp-aca-jobs-design.md`](../specs/2026-09-02-foundry-mcp-aca-jobs-design.md)

---

## Plan-time refinements

1. Unit and protocol contract tests live under `scripts/tests/`, not
   `skills/foundry-mcp-aca-jobs/tests/`. The repository's only unit-test command
   is `python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v`; placing
   tests under the skill would silently exclude them from CI.
2. Use a custom `ServerExtension` immediately. FastMCP 4.0.1's built-in
   `TasksExtension.lifespan()` starts Docket and its embedded worker. The new
   adapter reuses the pinned SEP-2663 Pydantic wire models and serializer shim
   from `fastmcp-tasks`, but never constructs `TasksExtension`, starts Docket,
   marks a tool `task=True`, or runs business code in the MCP process.
3. The internal task ID is deterministic and opaque:
   `uuid5(NAMESPACE_URL, ownerScope + ":" + jobType + ":" + idempotencyKeyHash)`.
   This permits a Cosmos point read after duplicate create while preserving the
   approved idempotency scope and request-fingerprint conflict check.
4. The callback receiver for the live fixture is an authenticated route on the
   same MCP Container App. The Job UAMI requests a token for the standing
   `MCP_AUTH_APP_CLIENT_ID` audience. This proves the managed-identity callback
   path without deploying a second receiver image.
5. Current catalog baseline is 35 skills, 31 upstream pins, 28 auto-tier pins,
   21 registered fixtures, and 575 unit tests. The implementation targets 36
   skills, 32 pins, 29 auto-tier pins, and 22 registered fixtures. Recompute the
   test total after adding this plan's tests; do not preserve the stale
   `AGENTS.md` value of 135.

---

## File structure

### New skill source

| File | Responsibility |
|---|---|
| `skills/foundry-mcp-aca-jobs/SKILL.md` | Version 1.0.0 consumer contract, protocol rules, security, deployment, operations, and failure semantics. |
| `skills/foundry-mcp-aca-jobs/README.md` | Short catalog-facing overview and canonical file map. |
| `skills/foundry-mcp-aca-jobs/references/python/app/__init__.py` | Package marker and public exports. |
| `skills/foundry-mcp-aca-jobs/references/python/app/models.py` | Enums, task records, requests, policies, errors, and status translation. |
| `skills/foundry-mcp-aca-jobs/references/python/app/control_store.py` | Store protocol, deterministic IDs, in-memory test store, and Cosmos ETag implementation. |
| `skills/foundry-mcp-aca-jobs/references/python/app/aca_jobs.py` | ACA client protocol, trusted execution-template construction, start/get/list/stop adapter, and Azure error translation. |
| `skills/foundry-mcp-aca-jobs/references/python/app/callbacks.py` | Alias allowlist, credential-free result URL validation, MI/Key Vault authentication, payload, and retries. |
| `skills/foundry-mcp-aca-jobs/references/python/app/orchestrator.py` | Start, status refresh, cancellation, and uncertain-start reconciliation. |
| `skills/foundry-mcp-aca-jobs/references/python/app/job_worker.py` | Worker claim, deterministic output, terminal persistence, and callback delivery. |
| `skills/foundry-mcp-aca-jobs/references/python/app/telemetry.py` | Safe OpenTelemetry spans, counters, histograms, and structured event attributes. |
| `skills/foundry-mcp-aca-jobs/references/python/app/aca_tasks_extension.py` | SEP-2663 methods and task-aware `tools/call` interception backed by the orchestrator. |
| `skills/foundry-mcp-aca-jobs/references/python/app/mcp_server.py` | FastMCP assembly, auth ownership extraction, fallback tools, health route, and reconciler lifespan. |
| `skills/foundry-mcp-aca-jobs/references/upstream-pin.md` | Tier-B package pins, FastMCP serializer known issue, executable import/wire validation, and audit record. |

### Deployment template

| File | Responsibility |
|---|---|
| `skills/foundry-mcp-aca-jobs/templates/pyproject.toml` | Runtime and test dependency caps. |
| `skills/foundry-mcp-aca-jobs/templates/Dockerfile` | One image containing both entrypoints. |
| `skills/foundry-mcp-aca-jobs/templates/azure.yaml` | One azd service build plus postdeploy image convergence and verification hooks. |
| `skills/foundry-mcp-aca-jobs/templates/infra/main.bicep` | Composition root for existing ACR/CAE, app, Job, Cosmos, storage, UAMIs, role definition, and role assignments. |
| `skills/foundry-mcp-aca-jobs/templates/infra/app.bicep` | MCP Container App using the shared digest and server command. |
| `skills/foundry-mcp-aca-jobs/templates/infra/cosmos.bicep` | Keyless Cosmos database/container with partition and unique-key policy. |
| `skills/foundry-mcp-aca-jobs/templates/infra/identity-rbac.bicep` | Separate UAMIs, custom ACA Job operator role, and data-plane grants. |
| `skills/foundry-mcp-aca-jobs/templates/infra/scripts/converge_image.py` | Resolve the single pushed digest and update app plus Job to that exact digest. |
| `skills/foundry-mcp-aca-jobs/templates/infra/scripts/verify_deployment.py` | Assert digest equality, commands, identities, and required outputs. |
| `skills/azd-patterns/references/bicep/aca-job.bicep` | Canonical reusable ACA Job resource module with digest, command, args, identity, registry, and environment inputs. |

### Tests and live fixture

| File | Responsibility |
|---|---|
| `scripts/tests/test_foundry_mcp_aca_jobs_models.py` | Lifecycle, ACA-state, and MCP-state mapping. |
| `scripts/tests/test_foundry_mcp_aca_jobs_store.py` | Idempotency, fingerprint conflicts, ETags, and terminal monotonicity. |
| `scripts/tests/test_foundry_mcp_aca_jobs_azure.py` | ARM start/get/list/stop and safe error translation. |
| `scripts/tests/test_foundry_mcp_aca_jobs_callbacks.py` | Alias/input/result URL policy, minimal payload, MI/KV auth, and retries. |
| `scripts/tests/test_foundry_mcp_aca_jobs_orchestrator.py` | Start, duplicate submission, cancellation races, and reconciliation. |
| `scripts/tests/test_foundry_mcp_aca_jobs_worker.py` | Worker-side task claim and duplicate-effect prevention. |
| `scripts/tests/test_foundry_mcp_aca_jobs_telemetry.py` | Redaction, stable attributes, counters, and latency recording. |
| `scripts/tests/test_foundry_mcp_aca_jobs_protocol.py` | In-process task negotiation, Tasks methods, fallback tools, and restart durability. |
| `scripts/tests/test_foundry_mcp_aca_jobs_template.py` | Shared-image, entrypoint, Bicep, RBAC, and fixture structural contracts. |
| `skills/foundry-mcp-aca-jobs/test-fixture/consumer_prompt.md` | Deterministic live Azure T3: deploy, direct Tasks client, fallback client, Prompt Agent, Hosted Agent, callback, cancellation, duplicate key, digest, and cleanup. |

### Repository integration

| File | Change |
|---|---|
| `skills/azd-patterns/SKILL.md` | Add canonical module guidance; bump 1.4.10 to 1.5.0. |
| `skills/foundry-mcp-aca/SKILL.md` | Add scope cross-reference; bump 1.2.4 to 1.2.5. |
| `.github/skill-deps.yml` | Register the new fixture and four dependencies. |
| `.github/workflows/skill-test.yml` | Install new unit dependencies and pass three MCP ACA Jobs CI secrets to initial/retry fixture steps. |
| `scripts/build-site.py` | Add the new skill to Foundry Building Blocks after `foundry-mcp-aca`. |
| `README.md` | Add the new catalog row. |
| `plugin.json` | Bump 4.29.6 to 4.30.0 and 35 to 36 skills. |
| `.github/plugin/marketplace.json` | Keep both version fields at 4.30.0 and both counts at 36. |
| `AGENTS.md` | Update §12.3 fixture count and §12.5 catalog metrics from measured values. |
| `docs/**` | Regenerate static site after all source changes. |

---

## Phase 0: lock upstream APIs before production code

### Task 1: Verify the pinned dependency and extension surface

**Files:**
- Create: `scripts/tests/test_foundry_mcp_aca_jobs_template.py`
- Create: `skills/foundry-mcp-aca-jobs/templates/pyproject.toml`

- [ ] **Step 1: Write the failing dependency-contract test**

Create the test module with this initial test:

```python
from __future__ import annotations

import pathlib
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-mcp-aca-jobs"


class FoundryMcpAcaJobsTemplateTests(unittest.TestCase):
    def test_dependency_caps_are_exact(self) -> None:
        data = tomllib.loads((SKILL / "templates" / "pyproject.toml").read_text())
        self.assertEqual(
            data["project"]["dependencies"],
            [
                "fastmcp~=4.0.1",
                "fastmcp-tasks~=4.0.1",
                "mcp~=2.1.1",
                "azure-cosmos[aio]~=4.16.4",
                "azure-identity~=1.25.3",
                "azure-keyvault-secrets~=4.11.2",
                "azure-mgmt-appcontainers~=5.0.0",
                "azure-monitor-opentelemetry~=1.8.9",
                "azure-storage-blob[aio]~=12.30.1",
                "httpx~=0.28.1",
                "pydantic~=2.13.5",
                "uvicorn~=0.52.4",
            ],
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
```

Expected: `ERROR` with `FileNotFoundError` for
`skills/foundry-mcp-aca-jobs/templates/pyproject.toml`.

- [ ] **Step 3: Add the minimal package manifest**

Create:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "foundry-mcp-aca-jobs-example"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
  "fastmcp~=4.0.1",
  "fastmcp-tasks~=4.0.1",
  "mcp~=2.1.1",
  "azure-cosmos[aio]~=4.16.4",
  "azure-identity~=1.25.3",
  "azure-keyvault-secrets~=4.11.2",
  "azure-mgmt-appcontainers~=5.0.0",
  "azure-monitor-opentelemetry~=1.8.9",
  "azure-storage-blob[aio]~=12.30.1",
  "httpx~=0.28.1",
  "pydantic~=2.13.5",
  "uvicorn~=0.52.4",
]

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] **Step 4: Run the focused test and install probe**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
python3 -m venv /tmp/mcp-aca-jobs-pin
. /tmp/mcp-aca-jobs-pin/bin/activate
pip install --quiet -r <(python3 - <<'PY'
import tomllib
for dep in tomllib.load(open("skills/foundry-mcp-aca-jobs/templates/pyproject.toml", "rb"))["project"]["dependencies"]:
    print(dep)
PY
)
python3 - <<'PY'
from fastmcp.server.extensions import MethodBinding, ServerExtension
from fastmcp_tasks.models import CreateTaskResult, GetTaskResult
from fastmcp_tasks import TasksExtension
assert "docket_lifespan" in __import__("inspect").getsource(TasksExtension.lifespan)
print("dependency and extension surface ok")
PY
```

Expected: one test passes and the probe prints
`dependency and extension surface ok`.

- [ ] **Step 5: Commit the dependency contract**

```bash
git add scripts/tests/test_foundry_mcp_aca_jobs_template.py \
  skills/foundry-mcp-aca-jobs/templates/pyproject.toml
git commit -m "test(foundry-mcp-aca-jobs): lock dependency surface [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 1: domain, persistence, and Azure boundaries

### Task 2: Define the task model and status translation

**Files:**
- Create: `skills/foundry-mcp-aca-jobs/references/python/app/__init__.py`
- Create: `skills/foundry-mcp-aca-jobs/references/python/app/models.py`
- Create: `scripts/tests/test_foundry_mcp_aca_jobs_models.py`

- [ ] **Step 1: Write failing lifecycle tests**

The test must cover all seven current ACA states:

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PYTHON = Path(__file__).resolve().parents[2] / "skills" / "foundry-mcp-aca-jobs" / "references" / "python"
sys.path.insert(0, str(PYTHON))

from app.models import LifecycleState, TaskRecord, map_aca_state, to_mcp_task


class StatusMappingTests(unittest.TestCase):
    def test_aca_state_mapping(self) -> None:
        task = TaskRecord.new("owner", "batch", "keyhash", "fingerprint", "https://example.com/in/1", "ops")
        expected = {
            "Processing": LifecycleState.STARTING,
            "Running": LifecycleState.RUNNING,
            "Succeeded": LifecycleState.RUNNING,
            "Failed": LifecycleState.FAILED,
            "Stopped": LifecycleState.FAILED,
            "Degraded": LifecycleState.STARTING,
            "Unknown": LifecycleState.STARTING,
        }
        for azure_state, state in expected.items():
            self.assertEqual(map_aca_state(task, azure_state).lifecycle_state, state)

    def test_cancelled_stopped_maps_to_cancelled(self) -> None:
        task = TaskRecord.new("owner", "batch", "keyhash", "fingerprint", "https://example.com/in/1", "ops")
        task.cancellation_requested_at = "2026-09-02T10:00:00Z"
        self.assertEqual(map_aca_state(task, "Stopped").lifecycle_state, LifecycleState.CANCELLED)

    def test_business_failure_is_completed_mcp_tool_error(self) -> None:
        task = TaskRecord.new("owner", "batch", "keyhash", "fingerprint", "https://example.com/in/1", "ops")
        task.lifecycle_state = LifecycleState.FAILED
        task.error_code = "ACA_EXECUTION_FAILED"
        result = to_mcp_task(task)
        self.assertEqual(result.status, "completed")
        self.assertTrue(result.result["isError"])
```

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_models -v
```

Expected: `ImportError` because `app.models` does not exist.

- [ ] **Step 3: Implement the minimal typed model**

Implement these public types and functions:

```python
class LifecycleState(StrEnum):
    ACCEPTED = "Accepted"
    STARTING = "Starting"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class CallbackDeliveryState(StrEnum):
    NOT_STARTED = "NotStarted"
    PENDING = "Pending"
    DELIVERED = "Delivered"
    EXHAUSTED = "Exhausted"


class TaskRecord(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda name: name.split("_")[0] + "".join(
            part.title() for part in name.split("_")[1:]),
    )
    task_id: str
    owner_scope: str
    job_type: str
    idempotency_key_hash: str
    request_fingerprint: str
    input_ref: AnyHttpUrl
    callback_alias: str
    lifecycle_state: LifecycleState = LifecycleState.ACCEPTED
    aca_execution_id: str | None = None
    result_url: AnyHttpUrl | None = None
    error_code: str | None = None
    callback_delivery_state: CallbackDeliveryState = CallbackDeliveryState.NOT_STARTED
    callback_error_code: str | None = None
    cancellation_requested_at: str | None = None
    start_attempted_at: str | None = None
    start_attempt_count: int = 0
    worker_claimed_at: str | None = None
    worker_claim_token: str | None = None
    worker_claim_expires_at: str | None = None
    created_at: str
    updated_at: str
    completed_at: str | None = None
    etag: str | None = Field(default=None, alias="_etag")

    @classmethod
    def new(cls, owner_scope: str, job_type: str, key_hash: str,
            fingerprint: str, input_ref: str, callback_alias: str) -> "TaskRecord":
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        task_id = str(uuid5(NAMESPACE_URL, f"{owner_scope}:{job_type}:{key_hash}"))
        return cls(task_id=task_id, owner_scope=owner_scope, job_type=job_type,
                   idempotency_key_hash=key_hash, request_fingerprint=fingerprint,
                   input_ref=input_ref, callback_alias=callback_alias,
                   created_at=now, updated_at=now)


class StartRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    job_type: str = Field(alias="jobType")
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=1, max_length=200)
    input_ref: AnyHttpUrl = Field(alias="inputRef")
    callback_alias: str = Field(alias="callbackAlias")
```

`map_aca_state()` must implement the spec table exactly. `to_mcp_task()` returns
a `GetTaskResult`; internal business failures return `status="completed"` with
`{"content": [{"type": "text", "text": error_code}], "isError": True}`.

- [ ] **Step 4: Run the tests and type import check**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_models -v
python3 -m py_compile skills/foundry-mcp-aca-jobs/references/python/app/*.py
```

Expected: all model tests pass; compile exits 0.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/references/python/app \
  scripts/tests/test_foundry_mcp_aca_jobs_models.py
git commit -m "feat(foundry-mcp-aca-jobs): define task lifecycle [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 3: Add allowlist and callback policy

**Files:**
- Modify: `skills/foundry-mcp-aca-jobs/references/python/app/models.py`
- Create: `skills/foundry-mcp-aca-jobs/references/python/app/callbacks.py`
- Create: `scripts/tests/test_foundry_mcp_aca_jobs_callbacks.py`

- [ ] **Step 1: Write failing policy tests**

```python
class CallbackPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = Policy(
            jobs={"batch": JobPolicy(resource_group="rg", job_name="batch-job",
                                     container_name="worker",
                                     image_digest="registry.azurecr.io/work@sha256:" + "a" * 64,
                                     command=["python", "-m", "app.job_worker"])},
            callbacks={"ops": CallbackPolicy(url="https://hooks.example.com/jobs",
                                             auth_mode="managed_identity",
                                             audience="api://mcp-callback")},
            input_hosts={"storage.example.com"},
            result_hosts={"storage.example.com"},
        )

    def test_rejects_unknown_alias_and_credential_url(self) -> None:
        with self.assertRaisesRegex(PublicError, "INVALID_CALLBACK_ALIAS"):
            self.policy.callback("https://attacker.example")
        with self.assertRaisesRegex(PublicError, "INVALID_INPUT_REFERENCE"):
            self.policy.validate_input("https://user:secret@storage.example.com/in/1")

    def test_callback_payload_is_minimal(self) -> None:
        payload = callback_payload("task", "execution", "Succeeded",
                                   "https://storage.example.com/results/task")
        self.assertEqual(set(payload), {"taskId", "acaExecutionId", "status", "resultUrl"})
```

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_callbacks -v
```

Expected: import failure for `Policy`.

- [ ] **Step 3: Implement policy and callback sender**

Add `JobPolicy`, `CallbackPolicy`, `Policy`, and `PublicError` to `models.py`.
`Policy.callback()` and `Policy.job()` use dictionary keys only.
`validate_input()` and `validate_result()` require HTTPS, no user info, and an
allowlisted host.

In `callbacks.py`, implement:

```python
def callback_payload(task_id: str, execution_id: str, status: str,
                     result_url: str) -> dict[str, str]:
    return {"taskId": task_id, "acaExecutionId": execution_id,
            "status": status, "resultUrl": result_url}


class CallbackSender:
    def __init__(self, client: httpx.AsyncClient, credential: AsyncTokenCredential,
                 secret_client: SecretClient | None = None) -> None:
        self._client = client
        self._credential = credential
        self._secret_client = secret_client

    async def send(self, policy: CallbackPolicy, payload: dict[str, str]) -> None:
        headers: dict[str, str] = {}
        if policy.auth_mode == "managed_identity":
            token = await self._credential.get_token(f"{policy.audience}/.default")
            headers["Authorization"] = f"Bearer {token.token}"
        elif policy.auth_mode == "key_vault":
            assert self._secret_client is not None and policy.secret_name is not None
            secret = await asyncio.to_thread(
                self._secret_client.get_secret, policy.secret_name)
            headers["X-Callback-Key"] = secret.value
        for attempt in range(5):
            try:
                response = await self._client.post(str(policy.url), json=payload,
                                                   headers=headers, timeout=10)
                response.raise_for_status()
                return
            except (httpx.TimeoutException, httpx.HTTPStatusError):
                if attempt == 4:
                    raise PublicError("CALLBACK_DELIVERY_EXHAUSTED")
                await asyncio.sleep(min(2 ** attempt, 8) + random.random())
```

- [ ] **Step 4: Run and verify green**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_callbacks -v
```

Expected: all callback tests pass, including retry exhaustion and no secret in
captured request JSON or logs.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/references/python/app/models.py \
  skills/foundry-mcp-aca-jobs/references/python/app/callbacks.py \
  scripts/tests/test_foundry_mcp_aca_jobs_callbacks.py
git commit -m "feat(foundry-mcp-aca-jobs): enforce target allowlists [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 4: Implement durable idempotent storage

**Files:**
- Create: `skills/foundry-mcp-aca-jobs/references/python/app/control_store.py`
- Create: `scripts/tests/test_foundry_mcp_aca_jobs_store.py`

- [ ] **Step 1: Write failing store tests**

Use `IsolatedAsyncioTestCase` to assert:

```python
async def test_duplicate_returns_same_task_and_fingerprint_conflict_fails(self) -> None:
    store = InMemoryControlStore()
    first = await store.create_or_get(self.task)
    duplicate = await store.create_or_get(self.task.model_copy())
    self.assertEqual(first.task_id, duplicate.task_id)
    changed = self.task.model_copy(update={"request_fingerprint": "different"})
    with self.assertRaisesRegex(PublicError, "IDEMPOTENCY_KEY_REUSED"):
        await store.create_or_get(changed)

async def test_etag_and_terminal_state_are_enforced(self) -> None:
    store = InMemoryControlStore()
    current = await store.create_or_get(self.task)
    stale = current.model_copy()
    updated = await store.replace(current.model_copy(
        update={"lifecycle_state": LifecycleState.STARTING}), current.etag)
    with self.assertRaises(ConcurrencyError):
        await store.replace(stale, stale.etag)
    with self.assertRaises(InvalidTransition):
        await store.replace(updated.model_copy(
            update={"lifecycle_state": LifecycleState.ACCEPTED}), updated.etag)
```

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_store -v
```

Expected: import failure for `control_store`.

- [ ] **Step 3: Implement the store protocol and in-memory store**

Define:

```python
class ControlStore(Protocol):
    async def create_or_get(self, task: TaskRecord) -> TaskRecord: ...
    async def get(self, owner_scope: str, task_id: str) -> TaskRecord: ...
    async def replace(self, task: TaskRecord, etag: str | None) -> TaskRecord: ...


TERMINAL = {LifecycleState.SUCCEEDED, LifecycleState.FAILED,
            LifecycleState.CANCELLED}
ALLOWED = {
    LifecycleState.ACCEPTED: {LifecycleState.ACCEPTED, LifecycleState.STARTING,
                              LifecycleState.FAILED, LifecycleState.CANCELLED},
    LifecycleState.STARTING: {LifecycleState.STARTING, LifecycleState.RUNNING,
                              LifecycleState.FAILED, LifecycleState.CANCELLED},
    LifecycleState.RUNNING: {LifecycleState.RUNNING, LifecycleState.SUCCEEDED,
                             LifecycleState.FAILED, LifecycleState.CANCELLED},
}
for state in TERMINAL:
    ALLOWED[state] = {state}
```

`InMemoryControlStore` uses `(owner_scope, task_id)` as key, increments a string
ETag on replace, and checks `ALLOWED`.

- [ ] **Step 4: Add Cosmos implementation and pass tests**

`CosmosControlStore` uses:

```python
await container.create_item(task.to_cosmos_item())
await container.read_item(item=task_id, partition_key=owner_scope)
await container.replace_item(
    item=task_id,
    body=task.to_cosmos_item(),
    etag=etag,
    match_condition=MatchConditions.IfNotModified,
)
```

Translate Cosmos 404 to `TASK_NOT_FOUND`, 409 with matching point-read to
duplicate resolution, and 412 to `ConcurrencyError`. Add mocked tests for all
three translations.

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_store -v
```

Expected: all store tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/references/python/app/control_store.py \
  scripts/tests/test_foundry_mcp_aca_jobs_store.py
git commit -m "feat(foundry-mcp-aca-jobs): add ETag task store [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 5: Implement the ACA Job management adapter

**Files:**
- Create: `skills/foundry-mcp-aca-jobs/references/python/app/aca_jobs.py`
- Create: `scripts/tests/test_foundry_mcp_aca_jobs_azure.py`

- [ ] **Step 1: Write failing ARM adapter tests**

Mock `ContainerAppsAPIClient` and assert that:

```python
execution = await adapter.start(policy, "owner-hash", "task-id")
client.jobs.begin_start.assert_called_once()
template = client.jobs.begin_start.call_args.args[2]
container = template.containers[0]
self.assertEqual(container.image, policy.image_digest)
self.assertEqual(container.command, ["python", "-m", "app.job_worker"])
self.assertEqual(container.args, ["--owner-scope", "owner-hash", "--task-id", "task-id"])
self.assertNotIn("inputRef", str(template))
self.assertNotIn("callback", str(template))
```

Also assert `get()` calls the single-execution API, `list()` is used only by
reconciliation, `stop()` calls the specific-execution API, and 403/404/429 map
to `TASK_FORBIDDEN`, `TASK_NOT_FOUND`, and retryable `ARM_STATUS_UNAVAILABLE`.

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_azure -v
```

Expected: import failure for `AcaJobsAdapter`.

- [ ] **Step 3: Implement the trusted template builder**

Define `AcaExecution` and `AcaJobsClient` protocol. In `AcaJobsAdapter.start()`,
first fetch the configured Job, verify its first container image equals
`policy.image_digest` and command equals `policy.command`, copy that container,
replace only `args`, and call `begin_start`. Reject mismatch with
`DEPLOYMENT_CONTRACT_MISMATCH`.

- [ ] **Step 4: Implement get/list/stop and run tests**

Use SDK 5.0.0 surfaces:

```python
await asyncio.to_thread(self._client.job_execution, resource_group, job, execution)
await asyncio.to_thread(lambda: list(
    self._client.jobs_executions.list(resource_group, job)))
poller = await asyncio.to_thread(
    self._client.jobs.begin_stop_execution, resource_group, job, execution)
await asyncio.to_thread(poller.result)
```

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_azure -v
```

Expected: all ARM adapter tests pass and none require `jobs/write`, delete,
list-secrets, or stop-multiple.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/references/python/app/aca_jobs.py \
  scripts/tests/test_foundry_mcp_aca_jobs_azure.py
git commit -m "feat(foundry-mcp-aca-jobs): add least-privilege ACA adapter [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 6: Implement orchestration and reconciliation

**Files:**
- Create: `skills/foundry-mcp-aca-jobs/references/python/app/orchestrator.py`
- Create: `scripts/tests/test_foundry_mcp_aca_jobs_orchestrator.py`

- [ ] **Step 1: Write failing start/idempotency tests**

Test `Orchestrator.start(StartRequest, owner_scope)` for:

- first request: `Accepted -> Starting`, one ARM call, bound execution;
- same scoped key and fingerprint: same task ID, no second ARM call;
- same key with different input: `IDEMPOTENCY_KEY_REUSED`;
- definitive ARM rejection: terminal `Failed` and raised `ARM_START_REJECTED`;
- timeout: return `Starting` with null execution ID.

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_orchestrator -v
```

Expected: import failure for `Orchestrator`.

- [ ] **Step 3: Implement minimal start/status/cancel**

Use SHA-256 over `owner_scope + "\0" + job_type + "\0" + idempotency_key` for
`idempotency_key_hash`, and canonical sorted JSON over
`jobType/inputRef/callbackAlias` for `request_fingerprint`.
Every store mutation retries a 412 at most three times by re-reading.

`cancel()` sets `cancellation_requested_at` before calling Azure. If no start
attempt occurred, transition directly to `Cancelled`; if start is uncertain,
do not retry start.

- [ ] **Step 4: Add reconciliation tests and code**

Test zero/one/multiple matching executions. Match a task only when the trusted
container's args contain the exact adjacent pair `--task-id`, task ID and the
execution start time is not earlier than `start_attempted_at`.

`reconcile()`:

```python
matches = [e for e in await jobs.list(policy)
           if e.matches_task(task.task_id, task.start_attempted_at)]
if len(matches) == 1:
    return await self._bind_and_refresh(task, matches[0])
if len(matches) > 1:
    winner = sorted(matches, key=lambda e: (e.start_time, e.execution_id))[0]
    for duplicate in matches:
        if duplicate.execution_id != winner.execution_id:
            await self._best_effort_stop(policy, duplicate.execution_id)
    return await self._bind_and_refresh(task, winner)
```

After three attempts or five minutes, transition to `Failed` with
`START_RECONCILIATION_EXHAUSTED`.

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_orchestrator -v
```

Expected: all orchestrator tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/references/python/app/orchestrator.py \
  scripts/tests/test_foundry_mcp_aca_jobs_orchestrator.py
git commit -m "feat(foundry-mcp-aca-jobs): reconcile durable executions [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 7: Implement the idempotent Job worker

**Files:**
- Create: `skills/foundry-mcp-aca-jobs/references/python/app/job_worker.py`
- Create: `scripts/tests/test_foundry_mcp_aca_jobs_worker.py`

- [ ] **Step 1: Write failing worker tests**

Use fake store, blob output, business handler, and callback sender. Assert:

1. first worker obtains a five-minute ETag lease, runs the handler once, writes
   `results/{taskId}/result.json`, persists a credential-free result URL, and
   sends the four-field callback;
2. second worker with the same task ID exits 0 without running the handler;
3. a worker can reclaim an expired lease after a crash and reuses an existing
   deterministic output object rather than repeating committed effects;
4. handler failure persists a stable worker code and no output URL;
5. callback exhaustion leaves lifecycle `Succeeded`, business `error_code`
   null, and callback state `Exhausted`.

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_worker -v
```

Expected: import failure for `JobWorker`.

- [ ] **Step 3: Implement worker claim and deterministic output**

`JobWorker.run(owner_scope, task_id)` must:

```python
task = await store.get(owner_scope, task_id)
if task.lifecycle_state in TERMINAL:
    return 0
if (task.worker_claim_expires_at
        and parse_time(task.worker_claim_expires_at) > datetime.now(UTC)):
    return 0
task.worker_claimed_at = utc_now()
task.worker_claim_token = str(uuid4())
task.worker_claim_expires_at = (
    datetime.now(UTC) + timedelta(minutes=5)
).isoformat().replace("+00:00", "Z")
task.lifecycle_state = LifecycleState.RUNNING
task = await store.replace(task, task.etag)
result = await handler(str(task.input_ref), task.task_id)
result_url = await output.write_json(
    f"results/{task.task_id}/result.json", result, overwrite=False)
```

The sample handler returns a small metadata object; it does not process work in
the MCP server.

- [ ] **Step 4: Implement terminal persistence and callback; run green**

If deterministic output already exists, read its metadata and continue without
repeating an external side effect. Persist success before callback delivery.
Catch callback exhaustion separately and update only
`callback_delivery_state` and `callback_error_code`.

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_worker -v
```

Expected: all worker tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/references/python/app/job_worker.py \
  scripts/tests/test_foundry_mcp_aca_jobs_worker.py
git commit -m "feat(foundry-mcp-aca-jobs): add idempotent job worker [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 7A: Add safe OpenTelemetry instrumentation

**Files:**
- Create: `skills/foundry-mcp-aca-jobs/references/python/app/telemetry.py`
- Create: `scripts/tests/test_foundry_mcp_aca_jobs_telemetry.py`
- Modify: `skills/foundry-mcp-aca-jobs/references/python/app/orchestrator.py`
- Modify: `skills/foundry-mcp-aca-jobs/references/python/app/job_worker.py`

- [ ] **Step 1: Write failing telemetry tests**

Use fake tracer, meter, counters, and histograms. Assert emitted attributes are
limited to `task.id`, `job.type`, `task.state`, `aca.execution.id`,
`operation`, `error.code`, and safe Azure request IDs. Pass strings containing
an idempotency key, input URL query, output body, bearer token, and Key Vault
secret; assert none appears in captured attributes or log records.

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_telemetry -v
```

Expected: import failure for `app.telemetry`.

- [ ] **Step 3: Implement the telemetry facade**

Implement one facade so business modules do not assemble ad hoc attributes:

```python
SAFE_KEYS = {
    "task.id", "job.type", "task.state", "aca.execution.id",
    "operation", "outcome", "error.code", "azure.request.id",
}


class Telemetry:
    def __init__(self, tracer=None, meter=None) -> None:
        self.tracer = tracer or trace.get_tracer("foundry-mcp-aca-jobs")
        self.meter = meter or metrics.get_meter("foundry-mcp-aca-jobs")
        self.operations = self.meter.create_counter("mcp_aca_jobs.operations")
        self.latency = self.meter.create_histogram(
            "mcp_aca_jobs.operation.duration", unit="s")

    def attributes(self, **values: str | None) -> dict[str, str]:
        return {key: value for key, value in values.items()
                if key in SAFE_KEYS and value is not None}

    @contextmanager
    def operation(self, name: str, attributes: dict[str, str]):
        started = monotonic()
        safe = self.attributes(**attributes, operation=name)
        with self.tracer.start_as_current_span(name, attributes=safe):
            try:
                yield
                self.operations.add(1, {**safe, "outcome": "success"})
            except Exception:
                self.operations.add(1, {**safe, "outcome": "failure"})
                raise
            finally:
                self.latency.record(monotonic() - started, safe)
```

`configure()` calls `configure_azure_monitor()` only when
`APPLICATIONINSIGHTS_CONNECTION_STRING` starts with `InstrumentationKey=` and
logs a safe warning otherwise.

- [ ] **Step 4: Instrument orchestration and worker; run green**

Wrap Cosmos create/replace, ACA start/get/list/stop, reconciliation, worker
claim, output persistence, and callback attempts. Add counters for duplicate
hits, ETag conflicts, cancellation, callback exhaustion, and digest mismatch.

Run:

```bash
python3 -m unittest \
  scripts.tests.test_foundry_mcp_aca_jobs_telemetry \
  scripts.tests.test_foundry_mcp_aca_jobs_orchestrator \
  scripts.tests.test_foundry_mcp_aca_jobs_worker -v
```

Expected: all tests pass and redaction assertions find no sensitive values.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/references/python/app/telemetry.py \
  skills/foundry-mcp-aca-jobs/references/python/app/orchestrator.py \
  skills/foundry-mcp-aca-jobs/references/python/app/job_worker.py \
  scripts/tests/test_foundry_mcp_aca_jobs_telemetry.py
git commit -m "feat(foundry-mcp-aca-jobs): add safe telemetry [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 2: MCP protocol and server

### Task 8: Implement the custom SEP-2663 adapter

**Files:**
- Create: `skills/foundry-mcp-aca-jobs/references/python/app/aca_tasks_extension.py`
- Create: `scripts/tests/test_foundry_mcp_aca_jobs_protocol.py`

- [ ] **Step 1: Write failing extension tests**

Construct `AcaTasksExtension` with fake orchestrator and owner resolver. Assert:

- `identifier == "io.modelcontextprotocol/tasks"`;
- methods are exactly `tasks/get`, `tasks/update`, `tasks/cancel`;
- task-aware `start_aca_job` returns `CreateTaskResult`;
- an unaware request calls the fallback continuation;
- another tool always calls the continuation;
- `tasks/get` returns `GetTaskResult`;
- `tasks/cancel` acknowledges and calls orchestrator cancel;
- `tasks/update` acknowledges without changing lifecycle;
- no `TasksExtension`, `TaskConfig`, Docket URL, or worker import occurs.

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_protocol -v
```

Expected: import failure for `AcaTasksExtension`.

- [ ] **Step 3: Implement the extension methods**

Use the public FastMCP surface:

```python
class AcaTasksExtension(ServerExtension):
    identifier = "io.modelcontextprotocol/tasks"

    def methods(self) -> Sequence[MethodBinding]:
        return (
            MethodBinding("tasks/get", GetTaskParams, self._get),
            MethodBinding("tasks/update", UpdateTaskParams, self._update),
            MethodBinding("tasks/cancel", CancelTaskParams, self._cancel),
        )

    async def intercept_tool_call(self, params, context, call_next):
        if params.name != "start_aca_job":
            return await call_next()
        if context.client_extension_settings(self.identifier) is None:
            return await call_next()
        request = StartRequest.model_validate(params.arguments or {})
        task = await self._orchestrator.start(
            request, self._owner_resolver(get_http_headers()))
        return CreateTaskResult(
            task_id=task.task_id, status="working",
            created_at=task.created_at, last_updated_at=task.updated_at,
            ttl_ms=86_400_000, poll_interval_ms=2_000)
```

Each `tasks/*` handler must verify per-request Tasks capability using
`self.client_settings(ctx)`. Missing capability raises `MCPError` with
`MISSING_REQUIRED_CLIENT_CAPABILITY` and `missing_capability_error_data()`.

- [ ] **Step 4: Add serializer-only lifespan and run green**

Because FastMCP 4.0.1 cannot otherwise emit the claimed task result, use:

```python
@asynccontextmanager
async def lifespan(self) -> AsyncIterator[None]:
    wire_production.install()
    try:
        yield
    finally:
        wire_production.uninstall()
```

Do not call `TasksExtension.lifespan()`. Add a test patching
`wire_production.install/uninstall` and asserting no Docket object is created.

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_protocol -v
```

Expected: all extension tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/references/python/app/aca_tasks_extension.py \
  scripts/tests/test_foundry_mcp_aca_jobs_protocol.py
git commit -m "feat(foundry-mcp-aca-jobs): map MCP Tasks to ACA [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 9: Assemble fallback tools and authenticated server

**Files:**
- Create: `skills/foundry-mcp-aca-jobs/references/python/app/mcp_server.py`
- Modify: `scripts/tests/test_foundry_mcp_aca_jobs_protocol.py`

- [ ] **Step 1: Add failing in-process fallback tests**

Build the server with in-memory store and fake ACA client. Through FastMCP
`Client`, call:

```python
started = await client.call_tool("start_aca_job", {
    "jobType": "batch", "idempotencyKey": "key-1",
    "inputRef": "https://storage.example.com/in/1",
    "callbackAlias": "ops",
})
status = await client.call_tool("get_aca_job_status",
                                {"taskId": started.data["taskId"]})
cancelled = await client.call_tool("cancel_aca_job",
                                   {"taskId": started.data["taskId"]})
```

Assert all calls return in under one second and the task ID is identical.

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_protocol -v
```

Expected: failure because `build_server()` does not exist.

- [ ] **Step 3: Implement server assembly and three tools**

`build_server(runtime: Runtime) -> FastMCP` registers
`AcaTasksExtension(runtime.orchestrator, resolve_owner_scope)`, `/health`,
the three tools, and an authenticated `/callbacks/jobs` route. The callback
route validates `CallbackEvent`, writes exactly its four fields to the
fixture-capable callback capture store, returns HTTP 202, and never proxies the
result URL. Use aliases in tool signatures so the JSON schema exposes exactly
`jobType`, `idempotencyKey`, `inputRef`, `callbackAlias`, and `taskId`.

`owner_scope_from_headers(headers, trusted=False)` fails closed unless the
runtime explicitly declares the ACA Easy Auth perimeter via
`MCP_ACA_JOBS_AUTH_MODE=aca-easy-auth`; only then may the verified
`X-MS-CLIENT-PRINCIPAL-ID` be hashed. Future Bicep must set that env var only
next to `authConfig.unauthenticatedClientAction=Return401`. Never trust a
caller-supplied owner.

Add this strict callback model to `models.py`:

```python
class CallbackEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    task_id: str = Field(alias="taskId")
    aca_execution_id: str = Field(alias="acaExecutionId")
    status: Literal["Succeeded", "Failed", "Cancelled"]
    result_url: AnyHttpUrl | None = Field(alias="resultUrl")
```

- [ ] **Step 4: Add restart and no-Docket assertions; run green**

Rebuild a second server around the same store after starting a task and verify
status retrieval. Inspect imported modules and assert no module beginning with
`pydocket` was loaded by server assembly.

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_protocol -v
```

Expected: all task-aware, unaware, cancellation, and restart tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/references/python/app/mcp_server.py \
  scripts/tests/test_foundry_mcp_aca_jobs_protocol.py
git commit -m "feat(foundry-mcp-aca-jobs): expose fallback tools [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 3: one-image azd deployment

### Task 10: Enforce one image and two entrypoints

**Files:**
- Create: `skills/foundry-mcp-aca-jobs/templates/Dockerfile`
- Modify: `scripts/tests/test_foundry_mcp_aca_jobs_template.py`

- [ ] **Step 1: Write failing Docker contract tests**

Assert one Dockerfile exists, copies the entire `app` package, exposes 8080,
contains no secret values, and has a neutral default:

```python
dockerfile = (SKILL / "templates" / "Dockerfile").read_text()
self.assertIn("COPY app ./app", dockerfile)
self.assertIn('CMD [\"python\", \"-m\", \"app.mcp_server\"]', dockerfile)
self.assertNotIn("app.job_worker", dockerfile.split("CMD", 1)[1])
self.assertEqual(len(list((SKILL / "templates").glob("Dockerfile*"))), 1)
```

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
```

Expected: `FileNotFoundError` for Dockerfile.

- [ ] **Step 3: Add the single Dockerfile**

```dockerfile
FROM python:3.12-slim
WORKDIR /srv
COPY pyproject.toml .
COPY app ./app
RUN pip install --no-cache-dir .
RUN python -m py_compile app/*.py
EXPOSE 8080
CMD ["python", "-m", "app.mcp_server"]
```

The Job command is supplied by Bicep, not by a second image or Docker stage.

- [ ] **Step 4: Build and run both entrypoints**

Run:

```bash
rm -rf /tmp/foundry-mcp-aca-jobs-image
mkdir -p /tmp/foundry-mcp-aca-jobs-image
cp skills/foundry-mcp-aca-jobs/templates/{Dockerfile,pyproject.toml} \
  /tmp/foundry-mcp-aca-jobs-image/
cp -R skills/foundry-mcp-aca-jobs/references/python/app \
  /tmp/foundry-mcp-aca-jobs-image/app
docker build -t foundry-mcp-aca-jobs:test \
  /tmp/foundry-mcp-aca-jobs-image
docker run --rm foundry-mcp-aca-jobs:test python -m app.mcp_server --help
docker run --rm foundry-mcp-aca-jobs:test python -m app.job_worker --help
```

Expected: image builds once; both commands exit 0 and print their CLI usage.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/templates/Dockerfile \
  scripts/tests/test_foundry_mcp_aca_jobs_template.py
git commit -m "feat(foundry-mcp-aca-jobs): ship shared runtime image [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 11: Add the canonical ACA Job module to azd-patterns

**Files:**
- Create: `skills/azd-patterns/references/bicep/aca-job.bicep`
- Modify: `skills/azd-patterns/SKILL.md`
- Modify: `scripts/tests/test_foundry_mcp_aca_jobs_template.py`

- [ ] **Step 1: Write the failing module contract test**

Assert the module:

- accepts `imageDigest`, `command`, `args`, `uamiResourceId`, `acrServer`,
  `environmentId`, and `environmentVariables`;
- requires the digest form with `@sha256:`;
- uses `Microsoft.App/jobs@2026-01-01`;
- sets trigger type `Manual`;
- sets explicit container `command` and `args`;
- contains no role assignment or product-specific names.

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
```

Expected: missing `aca-job.bicep`.

- [ ] **Step 3: Implement the canonical Bicep module**

The public contract is:

```bicep
param name string
param location string
param environmentId string
param imageDigest string
param containerName string
param command array
param args array = []
param environmentVariables array = []
param uamiResourceId string
param acrServer string
param replicaTimeout int = 300
param replicaRetryLimit int = 1

resource job 'Microsoft.App/jobs@2026-01-01' = {
  name: name
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${uamiResourceId}': {} }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: replicaTimeout
      replicaRetryLimit: replicaRetryLimit
      registries: [{ server: acrServer, identity: uamiResourceId }]
    }
    template: {
      containers: [{
        name: containerName
        image: imageDigest
        command: command
        args: args
        env: environmentVariables
        resources: { cpu: json('0.5'), memory: '1Gi' }
      }]
    }
  }
}
output id string = job.id
output name string = job.name
```

Add a Bicep assertion or deployment-script precondition that rejects a value
without `@sha256:`.

- [ ] **Step 4: Update azd-patterns and validate**

Bump `metadata.version` to `1.5.0`. Replace the current inline ACA Job resource
body in `## Bicep: ACA Job Pattern` with an imperative link to the new module,
document digest/command inputs, and preserve the job-only postdeploy limitation.

Run:

```bash
az bicep build --file skills/azd-patterns/references/bicep/aca-job.bicep \
  --outfile /tmp/aca-job.json
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
python3 scripts/validate-skills.py
```

Expected: Bicep builds, focused tests pass, and validator reports no broken
reference heading or SemVer error.

- [ ] **Step 5: Commit**

```bash
git add skills/azd-patterns/SKILL.md \
  skills/azd-patterns/references/bicep/aca-job.bicep \
  scripts/tests/test_foundry_mcp_aca_jobs_template.py
git commit -m "feat(azd-patterns): add canonical ACA Job module [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 12: Add app, data, identity, and RBAC Bicep

**Files:**
- Create: `skills/foundry-mcp-aca-jobs/templates/infra/app.bicep`
- Create: `skills/foundry-mcp-aca-jobs/templates/infra/cosmos.bicep`
- Create: `skills/foundry-mcp-aca-jobs/templates/infra/identity-rbac.bicep`
- Create: `skills/foundry-mcp-aca-jobs/templates/infra/main.bicep`
- Modify: `scripts/tests/test_foundry_mcp_aca_jobs_template.py`

- [ ] **Step 1: Write failing infrastructure contract tests**

Assert:

- app command is `["python", "-m", "app.mcp_server"]`;
- Job command passed to the canonical module is
  `["python", "-m", "app.job_worker"]`;
- both receive the same `imageDigest` parameter;
- two UAMIs are created;
- custom role actions equal exactly the five spec actions:
  `jobs/read`, `jobs/start/action`, `jobs/execution/read`,
  `jobs/executions/read`, `jobs/stop/execution/action`;
- no `jobs/write`, delete, list-secrets, stop-multiple, or Contributor grant;
- Cosmos partition path is `/ownerScope`, unique key path is
  `/idempotencyKeyHash`, and local auth is disabled;
- app and Job identities receive only their documented data roles.

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
```

Expected: missing infrastructure modules.

- [ ] **Step 3: Implement app and Cosmos modules**

`app.bicep` accepts one `imageDigest` and sets the explicit server command,
external HTTPS ingress, port 8080, UAMI registry pull, and health probe.
`main.bicep` defaults the first provision to the immutable bootstrap image
`mcr.microsoft.com/azuredocs/containerapps-helloworld@sha256:e9b3e7c34664c7cffd7144864b0e4eec369bfde80068f9095dc63b37058bec48`
for both resources. `azd deploy` replaces the app image, and the postdeploy
convergence hook replaces both resources with the single built ACR digest.

`cosmos.bicep` creates a serverless NoSQL account with `disableLocalAuth: true`,
one database, and one control container:

```bicep
resource control 'sqlDatabases/containers' = {
  parent: database
  name: 'tasks'
  properties: {
    resource: {
      id: 'tasks'
      partitionKey: { paths: ['/ownerScope'], kind: 'Hash', version: 2 }
      uniqueKeyPolicy: { uniqueKeys: [{ paths: ['/idempotencyKeyHash'] }] }
    }
  }
}
```

- [ ] **Step 4: Implement identities/RBAC and composition; validate**

Create a deterministic custom role definition with only:

```json
[
  "Microsoft.App/jobs/read",
  "Microsoft.App/jobs/start/action",
  "Microsoft.App/jobs/execution/read",
  "Microsoft.App/jobs/executions/read",
  "Microsoft.App/jobs/stop/execution/action"
]
```

Assign it to the MCP UAMI at the Job resource scope. Add ACR pull and Cosmos
data-plane roles separately to each identity. Pass the same digest to app and
Job, but pass distinct UAMI IDs and commands.

Run:

```bash
for f in skills/foundry-mcp-aca-jobs/templates/infra/*.bicep; do
  az bicep build --file "$f" --outfile "/tmp/$(basename "$f").json"
done
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
```

Expected: all Bicep files build and template tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/templates/infra/*.bicep \
  scripts/tests/test_foundry_mcp_aca_jobs_template.py
git commit -m "feat(foundry-mcp-aca-jobs): provision least-privilege runtime [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 13: Add one-build digest convergence and verification

**Files:**
- Create: `skills/foundry-mcp-aca-jobs/templates/azure.yaml`
- Create: `skills/foundry-mcp-aca-jobs/templates/infra/scripts/converge_image.py`
- Create: `skills/foundry-mcp-aca-jobs/templates/infra/scripts/verify_deployment.py`
- Modify: `scripts/tests/test_foundry_mcp_aca_jobs_template.py`

- [ ] **Step 1: Write failing one-build tests**

Assert `azure.yaml` has exactly one service with project `.`, host
`containerapp`, and one Dockerfile.
Assert postdeploy invokes `converge_image.py` then `verify_deployment.py`.
Assert both scripts reject tag-only images and compare exact digest plus exact
commands.

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
```

Expected: missing `azure.yaml`.

- [ ] **Step 3: Implement digest convergence**

`converge_image.py` reads azd environment values
`SERVICE_MCP_IMAGE_NAME`, `MCP_APP_NAME`, `ACA_JOB_NAME`, and
`AZURE_RESOURCE_GROUP`. Resolve the manifest digest with:

```python
host, remainder = image_name.split("/", 1)
registry = host.removesuffix(".azurecr.io")
repository, tag = remainder.rsplit(":", 1)
digest = subprocess.check_output(
    ["az", "acr", "manifest", "show-metadata",
     "--registry", registry, "--name", f"{repository}:{tag}",
     "--query", "digest", "-o", "tsv"], text=True).strip()
image_digest = f"{registry}.azurecr.io/{repository}@{digest}"
```

Fetch app and Job, set both first-container images to `image_digest`, preserve
their separate identities/configuration, and update only when drift exists.

- [ ] **Step 4: Implement verification and run local structural tests**

`verify_deployment.py` reads both Azure resources and requires:

```python
assert app_image == job_image == expected_image_digest
assert "@sha256:" in app_image
assert app_command == ["python", "-m", "app.mcp_server"]
assert job_command == ["python", "-m", "app.job_worker"]
assert app_uami_id != job_uami_id
```

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
python3 -m py_compile skills/foundry-mcp-aca-jobs/templates/infra/scripts/*.py
```

Expected: all tests pass and scripts compile.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/templates/azure.yaml \
  skills/foundry-mcp-aca-jobs/templates/infra/scripts \
  scripts/tests/test_foundry_mcp_aca_jobs_template.py
git commit -m "feat(foundry-mcp-aca-jobs): converge one immutable image [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 4: skill contract and freshness

### Task 14: Author SKILL.md, README, and upstream pin

**Files:**
- Create: `skills/foundry-mcp-aca-jobs/SKILL.md`
- Create: `skills/foundry-mcp-aca-jobs/README.md`
- Create: `skills/foundry-mcp-aca-jobs/references/upstream-pin.md`
- Modify: `skills/foundry-mcp-aca/SKILL.md`
- Modify: `scripts/tests/test_foundry_mcp_aca_jobs_template.py`

- [ ] **Step 1: Write failing documentation contract tests**

Assert fixed frontmatter shape, `metadata.version == "1.0.0"`, description
length 200-1024, all required headings from spec §§4-16, imperative links to
every canonical reference file, explicit no-Docket/no-Service-Bus/no-arbitrary-
URL rules, shared digest requirement, fallback tool names, all stable error
codes, and no duplicated Python function bodies.

Also assert `foundry-mcp-aca` points Job-backed tools to the new skill and bumps
to `1.2.5`.

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
```

Expected: missing `SKILL.md`.

- [ ] **Step 3: Write SKILL.md and README**

Use this heading order:

```text
# Foundry MCP ACA Jobs
## When to use this skill
## Architecture and shared-image contract
## Protocol contract
### Standards-first MCP Tasks path
### Compatibility tools
## Control record and lifecycle
## Idempotency and uncertain-start reconciliation
## Callback contract
## Security and least-privilege RBAC
## Deploy with azd
## Operate and observe
## Stable errors
## Test the implementation
## Non-goals
## Related skills
```

The frontmatter description must include `USE FOR` triggers for MCP Tasks, ACA
Jobs, long-running MCP tools, async MCP, Job callbacks, and external Job
orchestration; its `DO NOT USE FOR` routes general MCP hosting to
`foundry-mcp-aca`.

- [ ] **Step 4: Add the exact Tier-B pin and validate**

The pin lists the twelve versions from Task 1, `automation_tier: auto`,
`validation.requires: [pypi]`, and `runnable: true`. Add KI-001 documenting the
FastMCP 4.0.1 server-side claimed-result serializer shim; its release condition
is a public first-class server result-claim API.

The validation script installs bounded pins and imports every canonical module,
asserts the three extension methods, asserts `TasksExtension.lifespan` contains
`docket_lifespan`, asserts `AcaTasksExtension.lifespan` does not, and prints:

```text
ok fastmcp external tasks adapter
ok aca jobs sdk surface
ok foundry-mcp-aca-jobs imports
```

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
python3 scripts/validate-skills.py
```

Expected: focused tests pass; validation reports no frontmatter, description,
pin, reference-header, or cross-link error.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/SKILL.md \
  skills/foundry-mcp-aca-jobs/README.md \
  skills/foundry-mcp-aca-jobs/references/upstream-pin.md \
  skills/foundry-mcp-aca/SKILL.md \
  scripts/tests/test_foundry_mcp_aca_jobs_template.py
git commit -m "docs: add foundry MCP ACA Jobs skill [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 5: live consumer fixture

### Task 15: Add the deterministic Azure fixture contract

**Files:**
- Create: `skills/foundry-mcp-aca-jobs/test-fixture/consumer_prompt.md`
- Modify: `scripts/tests/test_foundry_mcp_aca_jobs_template.py`

- [ ] **Step 1: Write failing fixture structural tests**

Require:

- first Bash action is
  `echo "skills/foundry-mcp-aca-jobs/SKILL.md"`;
- no recursive `copilot`;
- exact marker `/tmp/foundry-mcp-aca-jobs-smoke-result`;
- UUID suffix;
- required env inventory for Azure, ACR, Foundry, Cosmos, storage, and auth app;
- explicit `azd auth login`;
- one build and captured digest;
- app/Job digest and command assertions;
- direct task-aware client, fallback client, Prompt Agent, Hosted Agent,
  callback, cancellation, duplicate idempotency, result URL, and cleanup gates;
- marker-first and best-effort teardown;
- no repository writes outside `.scratch/`.

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
```

Expected: missing fixture.

- [ ] **Step 3: Author fixture Steps -1 through 4**

The fixture must prescribe:

1. audit breadcrumb and anti-recursive guard;
2. auth/env checks and explicit azd OIDC login;
3. copy canonical template into
   `$GITHUB_WORKSPACE/.scratch/ci-smoke-mcp-jobs-$SUFFIX`;
4. inject standing brownfield values:
   `MCP_ACA_JOBS_COSMOS_ENDPOINT`,
   `MCP_ACA_JOBS_STORAGE_ACCOUNT_URL`, and `MCP_AUTH_APP_CLIENT_ID`;
5. run `azd up` once; and
6. query `az provider operation show --namespace Microsoft.App` and prove the
   five custom-role actions exist before deployment; and
7. read the app plus Job to prove exact digest equality and two commands.

If any required standing value is absent, write a precise FAIL marker. Do not
skip the relevant assertion.

- [ ] **Step 4: Author fixture Steps 5 through 10**

Prescribe exact hard gates:

1. direct Tasks client advertises `io.modelcontextprotocol/tasks`, starts a
   short job, polls `tasks/get`, and receives `completed` plus result URL;
2. unaware client gets ordinary tool data, uses status/cancel, and never gets a
   task result;
3. duplicate key returns same task ID and one deterministic result blob;
4. long job cancellation reaches `cancelled` or a documented race-safe
   completed result;
5. callback receiver captures exactly four fields and a credential-free URL;
6. Prompt Agent uses `MCPTool` pointed at the deployed URL and successfully
   calls fallback `start_aca_job` plus `get_aca_job_status`;
7. Hosted Agent uses `FoundryChatClient.get_mcp_tool` and proves the same two
   fallback tools;
8. write exact PASS marker; then perform five-minute best-effort targeted
   cleanup.

The direct client must use the real Tasks client extension rather than hand-
adding a metadata dictionary:

```python
from fastmcp import Client
from fastmcp_tasks.client import TasksClientExtension

async with Client(
    mcp_url,
    extensions=[TasksClientExtension()],
    auth=access_token,
) as client:
    result = await client.call_tool("start_aca_job", request)
```

The Prompt Agent smoke uses `AIProjectClient.agents.create_version()` with a
`PromptAgentDefinition` containing `MCPTool(server_label="aca_jobs",
server_url=mcp_url, headers={"Authorization": f"Bearer {access_token}"})`.
The Hosted Agent smoke uses
`FoundryChatClient.get_mcp_tool(name="ACA Jobs", url=mcp_url,
headers={"Authorization": f"Bearer {access_token}"},
approval_mode="never_require")` and passes that tool to `Agent`. Both prompts
must ask for `start_aca_job` followed by `get_aca_job_status`, and each smoke
must delete its agent artifact best-effort after recording its PASS evidence.

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
python3 scripts/validate-skills.py
```

Expected: fixture structural tests and catalog validation pass.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca-jobs/test-fixture/consumer_prompt.md \
  scripts/tests/test_foundry_mcp_aca_jobs_template.py
git commit -m "test(foundry-mcp-aca-jobs): add live Azure fixture [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 16: Register CI dependencies and environment

**Files:**
- Modify: `.github/skill-deps.yml`
- Modify: `.github/workflows/skill-test.yml`
- Modify: `scripts/tests/test_build_test_matrix.py`
- Modify: `scripts/tests/test_foundry_mcp_aca_jobs_template.py`

- [ ] **Step 1: Write failing graph/workflow tests**

Add assertions that:

```python
deps["skills"]["foundry-mcp-aca-jobs"]["depends_on"] == [
    "azd-patterns",
    "foundry-hosted-agents",
    "foundry-mcp-aca",
    "foundry-prompt-agents",
]
```

and both the initial and retry fixture env blocks contain:

```yaml
MCP_ACA_JOBS_COSMOS_ENDPOINT: ${{ secrets.MCP_ACA_JOBS_COSMOS_ENDPOINT }}
MCP_ACA_JOBS_STORAGE_ACCOUNT_URL: ${{ secrets.MCP_ACA_JOBS_STORAGE_ACCOUNT_URL }}
MCP_AUTH_APP_CLIENT_ID: ${{ secrets.MCP_AUTH_APP_CLIENT_ID }}
```

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest \
  scripts.tests.test_build_test_matrix \
  scripts.tests.test_foundry_mcp_aca_jobs_template -v
```

Expected: new dependency and env assertions fail.

- [ ] **Step 3: Add graph entry and unit dependencies**

Register the exact sorted dependency list. Extend workflow unit install with
the bounded packages required to import new modules. Do not add a separate E2E
job; the existing matrix discovers the fixture.

- [ ] **Step 4: Add byte-identical fixture env and run green**

Update the initial, retry1, and retry2 Copilot fixture env blocks. Use a test to
compare the three extracted mappings for equality.

Run:

```bash
python3 -m unittest \
  scripts.tests.test_build_test_matrix \
  scripts.tests.test_foundry_mcp_aca_jobs_template -v
python3 scripts/build-test-matrix.py --repo-root .
```

Expected: tests pass and matrix JSON contains
`"foundry-mcp-aca-jobs"`.

- [ ] **Step 5: Commit**

```bash
git add .github/skill-deps.yml .github/workflows/skill-test.yml \
  scripts/tests/test_build_test_matrix.py \
  scripts/tests/test_foundry_mcp_aca_jobs_template.py
git commit -m "ci: register foundry MCP ACA Jobs smoke [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 6: catalog and generated site

### Task 17: Integrate the new skill into the plugin catalog

**Files:**
- Modify: `README.md`
- Modify: `scripts/build-site.py`
- Modify: `plugin.json`
- Modify: `.github/plugin/marketplace.json`
- Modify: `AGENTS.md`

- [ ] **Step 1: Write failing catalog assertions**

Extend `test_foundry_mcp_aca_jobs_template.py` to assert:

- README has one row for `foundry-mcp-aca-jobs`;
- `CATEGORIES["🏗️ Foundry Building Blocks"]` contains the skill immediately after
  `foundry-mcp-aca`;
- both manifests report version `4.30.0` and 36 skills;
- AGENTS §12.3 reports the same 36/32/29/22 coverage totals and §12.5 reports
  36 skills, 32 pins, 29 auto-tier pins, and 22 fixtures.

- [ ] **Step 2: Run and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_foundry_mcp_aca_jobs_template -v
```

Expected: catalog assertions fail.

- [ ] **Step 3: Update catalog and manifests**

Add README description:

```text
Expose durable MCP tools backed by pre-provisioned ACA Jobs - SEP-2663 Tasks,
immediate fallback tools, Cosmos idempotency, managed-identity callbacks, and
one immutable image with separate server/worker entrypoints.
```

Bump plugin and marketplace versions from 4.29.6 to 4.30.0 and counts from 35
to 36.

- [ ] **Step 4: Recompute measured metrics and run catalog tests**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
print("skills", len(list(Path("skills").glob("*/SKILL.md"))))
print("pins", len(list(Path("skills").glob("*/references/upstream-pin.md"))))
print("fixtures", len(list(Path("skills").glob("*/test-fixture/consumer_prompt.md"))))
PY
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
```

Expected: counts are 36, 32, and 22; all tests pass. Record the emitted test
count in `AGENTS.md §12.5`, replacing 135 with the measured total.

- [ ] **Step 5: Commit**

```bash
git add README.md scripts/build-site.py plugin.json \
  .github/plugin/marketplace.json AGENTS.md \
  scripts/tests/test_foundry_mcp_aca_jobs_template.py
git commit -m "docs: register foundry MCP ACA Jobs skill [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 18: Rebuild and verify static documentation

**Files:**
- Modify: `docs/**`

- [ ] **Step 1: Run the site build**

Run:

```bash
python3 scripts/build-site.py --out docs/
```

Expected: exit 0 and generated skill page plus catalog entries for
`foundry-mcp-aca-jobs`.

- [ ] **Step 2: Verify generated references**

Run:

```bash
rg -l "foundry-mcp-aca-jobs" docs/ | sort
git add docs/
python3 scripts/build-site.py --out docs/
git diff --exit-code -- docs/
```

Expected: the new skill appears in generated HTML/LLM indexes; the second build
is byte-identical and `git diff --exit-code` exits 0 after staging the first
build.

- [ ] **Step 3: Run catalog validators**

Run:

```bash
python3 scripts/validate-skills.py
python3 scripts/build-plugins.py --check
```

Expected: both exit 0.

- [ ] **Step 4: Inspect forced-text scope**

Run:

```bash
git --no-pager diff -a --stat HEAD
git --no-pager diff -a HEAD -- skills/azd-patterns \
  skills/foundry-mcp-aca skills/foundry-mcp-aca-jobs \
  .github README.md AGENTS.md plugin.json scripts docs/
```

Expected: every change belongs to the allowlist in this plan; no reference data
or unrelated skill body changed.

- [ ] **Step 5: Commit**

```bash
git add docs/
git commit -m "docs: rebuild catalog for MCP ACA Jobs [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 7: complete local and live validation

### Task 19: Run the complete local quality gate

**Files:** none unless a failure identifies an implementation defect.

- [ ] **Step 1: Run focused behavioral tests**

```bash
python3 -m unittest \
  scripts.tests.test_foundry_mcp_aca_jobs_models \
  scripts.tests.test_foundry_mcp_aca_jobs_store \
  scripts.tests.test_foundry_mcp_aca_jobs_azure \
  scripts.tests.test_foundry_mcp_aca_jobs_callbacks \
  scripts.tests.test_foundry_mcp_aca_jobs_orchestrator \
  scripts.tests.test_foundry_mcp_aca_jobs_worker \
  scripts.tests.test_foundry_mcp_aca_jobs_protocol \
  scripts.tests.test_foundry_mcp_aca_jobs_template -v
```

Expected: all focused tests pass with zero failures/errors.

- [ ] **Step 2: Run full unit and catalog gates**

```bash
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
python3 scripts/validate-skills.py
python3 scripts/build-plugins.py --check
```

Expected: all tests pass and both validators exit 0.

- [ ] **Step 3: Run pin validation**

```bash
python3 scripts/run-pin-validation.py \
  --base="$(git merge-base origin/main HEAD)"
```

Expected output includes all three strings from Task 14 and exits 0.

- [ ] **Step 4: Run Bicep and image validation**

```bash
for f in skills/azd-patterns/references/bicep/aca-job.bicep \
  skills/foundry-mcp-aca-jobs/templates/infra/*.bicep; do
  az bicep build --file "$f" --outfile "/tmp/$(basename "$f").json"
done
rm -rf /tmp/foundry-mcp-aca-jobs-image
mkdir -p /tmp/foundry-mcp-aca-jobs-image
cp skills/foundry-mcp-aca-jobs/templates/{Dockerfile,pyproject.toml} \
  /tmp/foundry-mcp-aca-jobs-image/
cp -R skills/foundry-mcp-aca-jobs/references/python/app \
  /tmp/foundry-mcp-aca-jobs-image/app
docker build -t foundry-mcp-aca-jobs:test \
  /tmp/foundry-mcp-aca-jobs-image
docker run --rm foundry-mcp-aca-jobs:test python -m app.mcp_server --help
docker run --rm foundry-mcp-aca-jobs:test python -m app.job_worker --help
```

Expected: Bicep builds, image builds once, and both entrypoints exit 0.

- [ ] **Step 5: Commit only if verification required a fix**

For each defect, add a failing test first, apply the minimal fix, rerun the
focused and full commands, then commit the exact affected files:

```bash
git add skills/foundry-mcp-aca-jobs skills/azd-patterns \
  skills/foundry-mcp-aca scripts/tests .github README.md AGENTS.md \
  plugin.json docs
git commit -m "fix(foundry-mcp-aca-jobs): close validation gaps [skill-rewrite] [multi-skill]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

If no defect exists, do not create an empty commit.

### Task 20: Run the live Azure E2E and capture evidence

**Files:** no source changes unless the live test exposes a defect.

- [ ] **Step 1: Push the implementation branch and open the PR**

```bash
git push -u origin HEAD
gh pr create \
  --title "feat: add foundry MCP ACA Jobs skill" \
  --body "Adds the approved foundry-mcp-aca-jobs skill and canonical azd-patterns ACA Job module. Live Azure evidence will be appended from the skill-test matrix run."
```

Expected: PR URL is printed.

- [ ] **Step 2: Confirm the change-gated matrix contains the new leg**

```bash
PR=$(gh pr view --json number --jq .number)
gh run list --workflow "Skill tests" --branch "$(git branch --show-current)" \
  --limit 5 --json databaseId,status,conclusion,headSha
```

Expected: a run for current HEAD enters queued/in-progress and includes a
`foundry-mcp-aca-jobs` matrix job.

- [ ] **Step 3: Watch the run and inspect the exact leg**

```bash
RUN_ID=$(gh run list --workflow "Skill tests" \
  --branch "$(git branch --show-current)" --limit 1 \
  --json databaseId --jq '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status
gh run view "$RUN_ID" --json jobs \
  --jq '.jobs[] | select(.name | contains("foundry-mcp-aca-jobs")) |
        {name,conclusion,url}'
```

Expected: the leg concludes `success`.

- [ ] **Step 4: Verify transcript evidence**

Download the run artifact/log and require evidence for:

```text
SHARED_IMAGE_DIGEST_MATCH
RBAC_PROVIDER_ACTIONS_MATCH
MCP_TASKS_COMPLETED
FALLBACK_TOOLS_COMPLETED
IDEMPOTENCY_DUPLICATE_SAME_TASK
CALLBACK_PAYLOAD_VALID
CANCELLATION_TERMINAL
PROMPT_AGENT_MCP_PASS
HOSTED_AGENT_MCP_PASS
SMOKE_RESULT=PASS
```

Run:

```bash
gh run view "$RUN_ID" --log > "/tmp/foundry-mcp-aca-jobs-$RUN_ID.log"
for marker in SHARED_IMAGE_DIGEST_MATCH RBAC_PROVIDER_ACTIONS_MATCH \
  MCP_TASKS_COMPLETED \
  FALLBACK_TOOLS_COMPLETED IDEMPOTENCY_DUPLICATE_SAME_TASK \
  CALLBACK_PAYLOAD_VALID CANCELLATION_TERMINAL \
  PROMPT_AGENT_MCP_PASS HOSTED_AGENT_MCP_PASS SMOKE_RESULT=PASS; do
  rg -q -F "$marker" "/tmp/foundry-mcp-aca-jobs-$RUN_ID.log"
done
```

Expected: every grep exits 0.

- [ ] **Step 5: Add Azure evidence to the PR**

```bash
LEG_URL=$(gh run view "$RUN_ID" --json jobs --jq \
  '.jobs[] | select(.name | contains("foundry-mcp-aca-jobs")) | .url')
BODY=$(gh pr view "$PR" --json body --jq .body)
NEW_BODY="$BODY

## Live Azure evidence

- Skill-test run: https://github.com/aiappsgbb/awesome-gbb/actions/runs/$RUN_ID
- MCP ACA Jobs leg: $LEG_URL
- Verified one immutable digest on MCP app + ACA Job with distinct entrypoints.
- Verified SEP-2663 create/get/cancel, fallback tools, duplicate idempotency key, managed-identity callback, credential-free result URL, Prompt Agent MCP, and Hosted Agent MCP.
- Targeted cleanup ran best-effort after the deterministic PASS marker."
gh api --method PATCH "repos/aiappsgbb/awesome-gbb/pulls/$PR" \
  -f body="$NEW_BODY" --silent
```

Expected: PR body contains the run and job links.

---

## Final acceptance checklist

- [ ] `foundry-mcp-aca-jobs` exists at version 1.0.0 with valid fixed-shape frontmatter.
- [ ] MCP Tasks uses `AcaTasksExtension`; Docket never executes business work.
- [ ] Tasks-aware and unaware clients share one orchestrator and durable record.
- [ ] Cosmos record includes every approved field and all writes are ETag guarded.
- [ ] Duplicate scoped keys return one task; mismatched fingerprints fail.
- [ ] Uncertain starts reconcile by task ID and stop physical duplicates.
- [ ] Business effects and output paths are idempotent by task ID.
- [ ] Caller selects only job type, input reference, idempotency key, and callback alias.
- [ ] Callback is allowlisted, minimal, retried, and separate from business success.
- [ ] MCP and Job identities are separate and least privilege.
- [ ] One image is built once and both resources use the exact immutable digest.
- [ ] MCP app command is `python -m app.mcp_server`.
- [ ] ACA Job command is `python -m app.job_worker`.
- [ ] Canonical ACA Job Bicep lives in `azd-patterns`, not duplicated.
- [ ] Unit, protocol, image, Bicep, pin, and catalog tests pass.
- [ ] Live Azure proves Tasks, fallback, callback, cancellation, idempotency, digest, Prompt Agent, and Hosted Agent paths.
- [ ] Plugin and marketplace are both 4.30.0 and report 36 skills.
- [ ] Generated docs are rebuilt and byte-stable.
- [ ] PR body contains live Azure evidence.

---

## Self-review coverage map

| Approved-spec section | Implemented and verified by |
|---|---|
| §1 Decision / §2 goals | Tasks 2-20; final acceptance checklist |
| §3 non-goals | Task 14 documentation contract; Task 8 no-Docket assertions |
| §4 architecture and shared image | Tasks 10, 12, 13, 15, 19, 20 |
| §5 components/files | File structure plus Tasks 1-18 |
| §6 protocol contracts | Tasks 8, 9, 15, 20 |
| §7 Azure API/RBAC | Tasks 5, 12, 15, 20 |
| §8 data model | Tasks 2 and 4 |
| §9 lifecycle/state mapping | Task 2 and protocol tests in Task 8 |
| §10 idempotency/reconciliation | Tasks 4, 6, 7, 15, 20 |
| §11 callback behavior | Tasks 3, 7, 9, 15, 20 |
| §12 security | Tasks 3, 5, 9, 12, 14, 15 |
| §13 error semantics | Tasks 2-6 and Task 14 documentation assertions |
| §14 observability | Task 7A plus the live fixture's best-effort telemetry probe |
| §15 testing | Tasks 1-16, 19, and 20 |
| §16 rollout/compatibility | Tasks 8, 9, 14-18, and 20 |
| §17 risks | Dedicated tests for each risk in Tasks 3-15 |
| §18 references | Task 14 link and pin validation |

Self-review result: every approved requirement has an implementation task and
an explicit verification command. The plan contains no deferred implementation
markers, no unbound file names, and no alternate server/worker image path.

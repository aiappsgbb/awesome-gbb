---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    FastMCP 4 + ACA Job orchestration stack for job-backed MCP servers.
    The skill keeps a strict adapter boundary around the public Tasks
    result-claim path until upstream behavior is revalidated end to end.

packages:
  - name: fastmcp
    source: pypi
    version: "4.0.1"
    upstream_changelog: https://pypi.org/project/fastmcp/#history
    hold_below: "5.0.0"
    hold_reason: KI-001
    notes: |
      Canonical FastMCP runtime for the job-backed MCP server.
  - name: fastmcp-tasks
    source: pypi
    version: "4.0.1"
    upstream_changelog: https://pypi.org/project/fastmcp-tasks/#history
    hold_below: "5.0.0"
    hold_reason: KI-001
    notes: |
      SEP-2663 Tasks adapter package.
  - name: mcp
    source: pypi
    version: "2.1.1"
    upstream_changelog: https://pypi.org/project/mcp/#history
    hold_below: "3.0.0"
    hold_reason: KI-001
    notes: |
      MCP protocol package used by FastMCP and the Tasks compatibility path.
  - name: azure-cosmos
    source: pypi
    version: "4.16.4"
    upstream_changelog: https://pypi.org/project/azure-cosmos/#history
    notes: |
      Async Cosmos DB SDK used by the durable control store.
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    notes: |
      Managed identity auth for the app, worker, and callback delivery path.
  - name: azure-keyvault-secrets
    source: pypi
    version: "4.11.2"
    upstream_changelog: https://pypi.org/project/azure-keyvault-secrets/#history
    notes: |
      Optional callback secret retrieval when the policy uses key_vault auth.
  - name: azure-mgmt-appcontainers
    source: pypi
    version: "5.0.0"
    upstream_changelog: https://pypi.org/project/azure-mgmt-appcontainers/#history
    notes: |
      ACA management SDK for job start/read/stop and deployment verification.
  - name: azure-monitor-opentelemetry
    source: pypi
    version: "1.8.9"
    upstream_changelog: https://pypi.org/project/azure-monitor-opentelemetry/#history
    notes: |
      OpenTelemetry bridge for safe observability.
  - name: azure-storage-blob
    source: pypi
    version: "12.30.1"
    upstream_changelog: https://pypi.org/project/azure-storage-blob/#history
    notes: |
      Durable result and callback blob storage.
  - name: httpx
    source: pypi
    version: "0.28.1"
    upstream_changelog: https://pypi.org/project/httpx/#history
    notes: |
      Callback transport client.
  - name: pydantic
    source: pypi
    version: "2.13.5"
    upstream_changelog: https://pypi.org/project/pydantic/#history
    notes: |
      Strict request/record models and serialization.
  - name: uvicorn
    source: pypi
    version: "0.52.4"
    upstream_changelog: https://pypi.org/project/uvicorn/#history
    notes: |
      Local server runner for the MCP app.

docs_to_revalidate:
  - https://modelcontextprotocol.io/extensions/tasks/overview
  - https://github.com/modelcontextprotocol/ext-tasks/blob/main/specification/draft/tasks.md
  - https://gofastmcp.com/servers/tasks
  - https://gofastmcp.com/servers/extensions
  - https://learn.microsoft.com/en-us/azure/container-apps/jobs
  - https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/jobs/start?view=rest-resource-manager-containerapps-2026-01-01
  - https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/job-execution/job-execution?view=rest-resource-manager-containerapps-2026-01-01
  - https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/jobs-executions/list?view=rest-resource-manager-containerapps-2026-01-01
  - https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/jobs/stop-execution?view=rest-resource-manager-containerapps-2026-01-01
  - https://learn.microsoft.com/en-us/azure/cosmos-db/database-transactions-optimistic-concurrency
  - https://learn.microsoft.com/en-us/azure/container-apps/managed-identity
  - https://pypi.org/project/fastmcp/
  - https://pypi.org/project/fastmcp-tasks/
  - https://pypi.org/project/mcp/
  - https://pypi.org/project/azure-cosmos/
  - https://pypi.org/project/azure-identity/
  - https://pypi.org/project/azure-keyvault-secrets/
  - https://pypi.org/project/azure-mgmt-appcontainers/
  - https://pypi.org/project/azure-monitor-opentelemetry/
  - https://pypi.org/project/azure-storage-blob/
  - https://pypi.org/project/httpx/
  - https://pypi.org/project/pydantic/
  - https://pypi.org/project/uvicorn/

known_issues:
  - id: KI-001
    description: FastMCP's claimed-result serializer shim and Tasks adapter remain an upstream compatibility boundary. Keep the adapter seam in the skill until the public Tasks result-claim API is revalidated end to end.
    upstream_url: https://github.com/PrefectHQ/fastmcp/issues/2754
    status: open
    workaround_location: SKILL.md § Standards-first MCP Tasks path

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    REPO_ROOT="${PIN_VALIDATION_REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
    if [[ -z "$REPO_ROOT" ]] || ! git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      echo "ERROR: could not determine repository root; set PIN_VALIDATION_REPO_ROOT or run this validation from inside the awesome-gbb git repository." >&2
      exit 1
    fi
    python -m venv .venv
    . .venv/bin/activate
    export PYTHONPATH="$REPO_ROOT/skills/foundry-mcp-aca-jobs/references/python${PYTHONPATH:+:$PYTHONPATH}"
    pip install --quiet       "fastmcp~=4.0.1"       "fastmcp-tasks~=4.0.1"       "mcp~=2.1.1"       "azure-cosmos[aio]~=4.16.4"       "azure-identity~=1.25.3"       "azure-keyvault-secrets~=4.11.2"       "azure-mgmt-appcontainers~=5.0.0"       "azure-monitor-opentelemetry~=1.8.9"       "azure-storage-blob[aio]~=12.30.1"       "httpx~=0.28.1"       "pydantic~=2.13.5"       "uvicorn~=0.52.4"
    python - <<'PY'
    import inspect
    from azure.mgmt.appcontainers.operations import JobsOperations, JobsExecutionsOperations
    from fastmcp.server.extensions import ServerExtension
    from fastmcp_tasks import TasksExtension
    from app.aca_jobs import AcaExecution, AcaJobsAdapter, AcaJobsClient
    from app.aca_tasks_extension import AcaTasksExtension
    from app.callbacks import AsyncTokenCredential, CallbackSender, callback_payload
    from app.control_store import ControlStore, CosmosControlStore, InMemoryControlStore
    from app.job_worker import JobWorker, build_arg_parser as build_worker_arg_parser, build_worker_from_env, demo_handler
    from app.mcp_server import Runtime, build_server, owner_scope_from_headers, runtime_from_env
    from app.models import CallbackDeliveryState, CallbackEvent, CallbackPolicy, GetTaskResult, JobPolicy, LifecycleState, Policy, PublicError, StartRequest, TaskRecord, map_aca_state, to_mcp_task
    from app.orchestrator import Orchestrator
    from app.telemetry import Telemetry, configure, telemetry

    assert issubclass(AcaTasksExtension, ServerExtension), "AcaTasksExtension must stay a FastMCP ServerExtension"
    assert hasattr(AcaTasksExtension, "methods"), "AcaTasksExtension.methods missing"
    assert hasattr(AcaTasksExtension, "intercept_tool_call"), "AcaTasksExtension.intercept_tool_call missing"
    assert hasattr(AcaTasksExtension, "lifespan"), "AcaTasksExtension.lifespan missing"
    tasks_source = inspect.getsource(TasksExtension.lifespan)
    aca_source = inspect.getsource(AcaTasksExtension.lifespan)
    assert "docket_lifespan" in tasks_source, "TasksExtension.lifespan must expose docket_lifespan"
    assert "docket_lifespan" not in aca_source, "AcaTasksExtension.lifespan must not leak Docket lifecycle wiring"

    assert hasattr(JobsOperations, "get"), "JobsOperations.get missing"
    assert hasattr(JobsOperations, "begin_start"), "JobsOperations.begin_start missing"
    assert hasattr(JobsOperations, "begin_stop_execution"), "JobsOperations.begin_stop_execution missing"
    assert hasattr(JobsExecutionsOperations, "list"), "JobsExecutionsOperations.list missing"

    assert callable(callback_payload)
    assert callable(CallbackSender)
    assert callable(to_mcp_task)
    assert callable(map_aca_state)
    assert callable(build_server)
    assert callable(build_worker_from_env)
    assert callable(build_worker_arg_parser)
    assert callable(demo_handler)
    print("ok fastmcp external tasks adapter")
    print("ok aca jobs sdk surface")
    print("ok foundry-mcp-aca-jobs imports")
    PY
  expected_output:
    - "ok fastmcp external tasks adapter"
    - "ok aca jobs sdk surface"
    - "ok foundry-mcp-aca-jobs imports"

last_validated: 2026-09-02
validated_by: copilot-bot
known_issues_count: 1
---

# Upstream pin — `foundry-mcp-aca-jobs` skill

This Tier-B pin captures the FastMCP 4 / MCP 2 / ACA Job stack for the job-backed
Foundry MCP pattern. It intentionally avoids live Azure validation.

## Pinned packages

| Package | Source | Pinned version | Notes |
|---|---|---|---|
| `fastmcp` | PyPI | **4.0.1** | Canonical FastMCP runtime |
| `fastmcp-tasks` | PyPI | **4.0.1** | SEP-2663 Tasks adapter |
| `mcp` | PyPI | **2.1.1** | MCP protocol package |
| `azure-cosmos[aio]` | PyPI | **4.16.4** | Async control-store SDK |
| `azure-identity` | PyPI | **1.25.3** | Managed identity auth |
| `azure-keyvault-secrets` | PyPI | **4.11.2** | Optional callback secret path |
| `azure-mgmt-appcontainers` | PyPI | **5.0.0** | ACA Job control-plane SDK |
| `azure-monitor-opentelemetry` | PyPI | **1.8.9** | Safe telemetry bridge |
| `azure-storage-blob[aio]` | PyPI | **12.30.1** | Result/callback blob storage |
| `httpx` | PyPI | **0.28.1** | Callback transport |
| `pydantic` | PyPI | **2.13.5** | Control-record models |
| `uvicorn` | PyPI | **0.52.4** | Local server runner |

## Verification checklist

Run the `validation.script` front-matter block. Expected output must match the
three exact markers above:

- `ok fastmcp external tasks adapter`
- `ok aca jobs sdk surface`
- `ok foundry-mcp-aca-jobs imports`

## Known issues

### KI-001 — FastMCP claimed-result serializer shim

FastMCP's claimed-result serializer shim and Tasks adapter are still an upstream
compatibility boundary. Keep the adapter seam in the skill until the public
Tasks result-claim API is revalidated end to end.

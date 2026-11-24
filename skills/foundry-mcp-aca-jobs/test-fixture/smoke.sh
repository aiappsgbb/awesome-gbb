#!/usr/bin/env bash
# Canonical foundry-mcp-aca-jobs CI smoke. Run as-is: bash skills/foundry-mcp-aca-jobs/test-fixture/smoke.sh
set -Eeuo pipefail
MARKER=/tmp/foundry-mcp-aca-jobs-smoke-result
# Internal deadline: finish (FAIL marker + failure-path cleanup) well inside the
# 120-minute job timeout instead of being cancelled with no result (#488).
SMOKE_DEADLINE_SECONDS="${SMOKE_DEADLINE_SECONDS:-4200}"
if [[ -z "${SMOKE_UNDER_DEADLINE:-}" ]]; then
  rm -f "$MARKER"
  set +e
  SMOKE_UNDER_DEADLINE=1 timeout --kill-after=900 "$SMOKE_DEADLINE_SECONDS" bash "$0" "$@"
  status=$?
  set -e
  if [[ "$status" -eq 124 || "$status" -eq 137 ]]; then
    grep -q '^SMOKE_RESULT=FAIL' "$MARKER" 2>/dev/null ||
      printf 'SMOKE_RESULT=FAIL internal deadline %ss exceeded\n' "$SMOKE_DEADLINE_SECONDS" > "$MARKER"
  fi
  exit "$status"
fi
trap 'exit 143' TERM
EVIDENCE=/tmp/foundry-mcp-aca-jobs-smoke-evidence
rm -f "$MARKER"
# Diagnostics for the uploaded evidence file; tokens never reach it.
redact() {
  sed -E 's/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/<redacted-jwt>/g; s/([Bb]earer)[[:space:]]+[^[:space:]]+/\1 <redacted>/g'
}

fail() {
  printf 'SMOKE_RESULT=FAIL %s\n' "$1" > "$MARKER"
  exit 1
}
on_error() {
  local status=$?
  trap - ERR
  if [[ ! -f "$MARKER" ]]; then
    printf 'SMOKE_RESULT=FAIL hard abort at line %s (exit %s)\n' "$1" "$status" > "$MARKER"
  fi
  exit "$status"
}
trap 'on_error "$LINENO"' ERR
# Best-effort failure-path cleanup (Pattern 25): only the exact objects that
# ci_reuse.py recorded as created by this run; the FAIL marker is unchanged.
cleanup_on_failure() {
  local status=$?
  [[ "$status" -ne 0 && -n "${PROJECT_DIR:-}" && -f "$PROJECT_DIR/ci-run-owned.json" ]] || return 0
  trap - ERR
  set +e
  if [[ -n "${APP_NAME:-}" && -n "${CHILD_RG:-}" ]]; then
    {
      echo "== app console (tail) =="
      timeout 90 az containerapp logs show --resource-group "$CHILD_RG" --name "$APP_NAME" \
        --tail 200 --format text 2>&1 | grep -v "GET /health"
      echo "== job executions =="
      timeout 60 az containerapp job execution list --resource-group "$CHILD_RG" \
        --name "$JOB_NAME" --output table 2>&1
    } | redact >> "$EVIDENCE"
  fi
  # Invocation custody records hold only hashes, IDs and status codes; publish
  # them so an unresolved invoke is diagnosable from the artifact.
  for record in "$PROJECT_DIR"/ci-*-operation.jsonl; do
    [[ -f "$record" ]] || continue
    { echo "== $(basename "$record") =="; cat "$record"; } | redact >> "$EVIDENCE"
  done
  local helper="$PROJECT_DIR/infra/scripts/ci_reuse.py"
  [[ -f "$PROJECT_DIR/ci-created.json" ]] || python3 "$helper" record --project "$PROJECT_DIR"
  if python3 "$helper" cleanup --project "$PROJECT_DIR" --execute; then
    [[ ! -f "$PROJECT_DIR/ci-image.json" ]] ||
      python3 "$helper" cleanup-image --project "$PROJECT_DIR" --execute
    echo "NOTE failure-path run-owned cleanup attempted; see output above"
  else
    echo "NOTE failure-path cleanup incomplete; report run-owned residuals"
  fi
}
trap cleanup_on_failure EXIT

echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "ACR_LOGIN_SERVER=${ACR_LOGIN_SERVER:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
echo "AZURE_AI_PROJECT_ID=${AZURE_AI_PROJECT_ID:+set}"
echo "FOUNDRY_MODEL_DEPLOYMENT=${FOUNDRY_MODEL_DEPLOYMENT:+set}"
echo "MCP_AUTH_APP_CLIENT_ID=${MCP_AUTH_APP_CLIENT_ID:+set}"
echo "MCP_ACA_JOBS_COSMOS_ENDPOINT=${MCP_ACA_JOBS_COSMOS_ENDPOINT:+set}"
echo "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL=${MCP_ACA_JOBS_STORAGE_ACCOUNT_URL:+set}"

test -n "${AZURE_CLIENT_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL missing AZURE_CLIENT_ID\n' > "$MARKER"; exit 1;
}
test -n "${AZURE_TENANT_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL missing AZURE_TENANT_ID\n' > "$MARKER"; exit 1;
}
test -n "${AZURE_SUBSCRIPTION_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL missing AZURE_SUBSCRIPTION_ID\n' > "$MARKER"; exit 1;
}
test -n "${ACR_LOGIN_SERVER:-}" || {
  printf 'SMOKE_RESULT=FAIL missing ACR_LOGIN_SERVER\n' > "$MARKER"; exit 1;
}
test -n "${FOUNDRY_PROJECT_ENDPOINT:-}" || {
  printf 'SMOKE_RESULT=FAIL missing FOUNDRY_PROJECT_ENDPOINT\n' > "$MARKER"; exit 1;
}
test -n "${AZURE_AI_PROJECT_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL missing AZURE_AI_PROJECT_ID\n' > "$MARKER"; exit 1;
}
test -n "${FOUNDRY_MODEL_DEPLOYMENT:-}" || {
  printf 'SMOKE_RESULT=FAIL missing FOUNDRY_MODEL_DEPLOYMENT\n' > "$MARKER"; exit 1;
}
test -n "${MCP_AUTH_APP_CLIENT_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL missing MCP_AUTH_APP_CLIENT_ID\n' > "$MARKER"; exit 1;
}
test -n "${MCP_ACA_JOBS_COSMOS_ENDPOINT:-}" || {
  printf 'SMOKE_RESULT=FAIL missing MCP_ACA_JOBS_COSMOS_ENDPOINT\n' > "$MARKER"; exit 1;
}
test -n "${MCP_ACA_JOBS_STORAGE_ACCOUNT_URL:-}" || {
  printf 'SMOKE_RESULT=FAIL missing MCP_ACA_JOBS_STORAGE_ACCOUNT_URL\n' > "$MARKER"; exit 1;
}

az account show --output table || echo "(az cache not inherited — relying on azd auth login below)"
azd auth login \
  --federated-credential-provider github \
  --client-id "$AZURE_CLIENT_ID" \
  --tenant-id "$AZURE_TENANT_ID" || {
  printf 'SMOKE_RESULT=FAIL azd auth login failed\n' > "$MARKER"; exit 1;
}

## Step 1 — goal and constraints

SUFFIX="$(uuidgen | tr 'A-Z' 'a-z' | cut -c1-8)"
SCRATCH_ROOT="$GITHUB_WORKSPACE/.scratch/ci-smoke-mcp-jobs-$SUFFIX"
PROJECT_DIR="$SCRATCH_ROOT/skills/foundry-mcp-aca-jobs/templates"
CANONICAL_JOB_DIR="$SCRATCH_ROOT/skills/azd-patterns/references/bicep"
AZD_ENV_NAME="ci-smoke-mcp-jobs-$SUFFIX"
APP_NAME="ci-smoke-mcp-jobs-$SUFFIX"
JOB_NAME="ci-smoke-mcp-jobs-w-$SUFFIX"
HOSTED_NAME="ci-smoke-mcp-jobs-hosted-$SUFFIX"
ACR_NAME="${ACR_LOGIN_SERVER%%.*}"
export MCP_ACA_JOBS_CI_REUSE=existing
test -n "${MCP_ACA_JOBS_RESOURCE_GROUP_ID:-}" || fail "missing standing resource group ID"
test -n "${MCP_ACA_JOBS_COSMOS_DATABASE:-}" || fail "missing standing Cosmos database"
test -n "${MCP_ACA_JOBS_ENVIRONMENT_ID:-}" || fail "missing standing environment ID"
CHILD_RG="${MCP_ACA_JOBS_RESOURCE_GROUP_ID##*/}"
MCP_ACA_JOBS_PLATFORM_RESOURCE_GROUP="$CHILD_RG"
MCP_ACA_JOBS_ENVIRONMENT_NAME="${MCP_ACA_JOBS_ENVIRONMENT_ID##*/}"
MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME="mcpjobs-$SUFFIX"
MCP_ACA_JOBS_COSMOS_CONTAINER="ci-smoke-mcp-jobs-task-$SUFFIX"
MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME="$(
  python3 -c 'import os,urllib.parse; print((urllib.parse.urlsplit(os.environ["MCP_ACA_JOBS_STORAGE_ACCOUNT_URL"]).hostname or "").split(".")[0])'
)"
MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME="$(
  python3 -c 'import os,urllib.parse; print((urllib.parse.urlsplit(os.environ["MCP_ACA_JOBS_COSMOS_ENDPOINT"]).hostname or "").split(".")[0])'
)"
test -n "${MCP_ACA_JOBS_CALLER_PRINCIPAL_ID:-}" || fail "missing standing executor principal"
export SUFFIX SCRATCH_ROOT PROJECT_DIR CANONICAL_JOB_DIR
export CHILD_RG AZD_ENV_NAME APP_NAME JOB_NAME HOSTED_NAME
export ACR_NAME MCP_ACA_JOBS_PLATFORM_RESOURCE_GROUP
export MCP_ACA_JOBS_ENVIRONMENT_NAME MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME
export MCP_ACA_JOBS_COSMOS_DATABASE MCP_ACA_JOBS_COSMOS_CONTAINER
export MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME
export MCP_ACA_JOBS_CALLER_PRINCIPAL_ID

[[ "$SCRATCH_ROOT" == "$GITHUB_WORKSPACE/.scratch/"* ]] ||
  fail "scratch workspace escaped GITHUB_WORKSPACE/.scratch"
# CHILD_RG is retained as the fixture's workload-scope variable, not a new RG.

## Step 2 — deterministic scaffold

mkdir -p "$PROJECT_DIR" "$CANONICAL_JOB_DIR"
cp skills/foundry-mcp-aca-jobs/templates/azure.yaml "$PROJECT_DIR/azure.yaml"
cp skills/foundry-mcp-aca-jobs/templates/Dockerfile "$PROJECT_DIR/Dockerfile"
cp skills/foundry-mcp-aca-jobs/templates/.dockerignore "$PROJECT_DIR/.dockerignore"
cp skills/foundry-mcp-aca-jobs/templates/.azdignore "$PROJECT_DIR/.azdignore"
cp skills/foundry-mcp-aca-jobs/templates/pyproject.toml "$PROJECT_DIR/pyproject.toml"
cp skills/foundry-mcp-aca-jobs/templates/uv.lock "$PROJECT_DIR/uv.lock"
cp skills/foundry-mcp-aca-jobs/templates/bicepconfig.json "$PROJECT_DIR/bicepconfig.json"
cp -R skills/foundry-mcp-aca-jobs/templates/infra "$PROJECT_DIR/infra"
cp skills/azd-patterns/references/bicep/aca-job.bicep "$CANONICAL_JOB_DIR/aca-job.bicep"
cp -R skills/foundry-mcp-aca-jobs/references/python/app "$PROJECT_DIR/app"
cp skills/foundry-hosted-agents/references/python/operation_evidence.py "$PROJECT_DIR/operation_evidence.py"
mkdir -p "$PROJECT_DIR/.azure/$AZD_ENV_NAME"

# Authenticated GET/list preflight validates exact standing bindings, runtime
# writers vs executor reader, and absence of every run target BEFORE any write.
python3 "$PROJECT_DIR/infra/scripts/ci_reuse.py" prepare \
  --project "$PROJECT_DIR" --run-id "$SUFFIX" || fail "standing reuse preflight blocked"
CI_LOCATION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["parameters"]["location"]["value"])' "$PROJECT_DIR/infra/main.parameters.json")"

cat > "$PROJECT_DIR/.azure/config.json" <<EOF
{"defaultEnvironment":"$AZD_ENV_NAME"}
EOF
cat > "$PROJECT_DIR/.azure/$AZD_ENV_NAME/.env" <<EOF
AZURE_ENV_NAME="$AZD_ENV_NAME"
AZURE_LOCATION="$CI_LOCATION"
AZURE_RESOURCE_GROUP="$CHILD_RG"
AZURE_SUBSCRIPTION_ID="$AZURE_SUBSCRIPTION_ID"
AZURE_TENANT_ID="$AZURE_TENANT_ID"
AZURE_CLIENT_ID="$AZURE_CLIENT_ID"
ACR_NAME="$ACR_NAME"
ACR_LOGIN_SERVER="$ACR_LOGIN_SERVER"
MCP_ACA_JOBS_PLATFORM_RESOURCE_GROUP="$MCP_ACA_JOBS_PLATFORM_RESOURCE_GROUP"
MCP_ACA_JOBS_ENVIRONMENT_NAME="$MCP_ACA_JOBS_ENVIRONMENT_NAME"
MCP_ACA_JOBS_APP_NAME="$APP_NAME"
MCP_ACA_JOBS_JOB_NAME="$JOB_NAME"
MCP_ACA_JOBS_STORAGE_ACCOUNT_URL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["storage_endpoint"])' "$PROJECT_DIR/ci-reuse.json")"
MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME="$MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME"
MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME="$MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME"
MCP_ACA_JOBS_COSMOS_ENDPOINT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["cosmos_endpoint"])' "$PROJECT_DIR/ci-reuse.json")"
MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME="$MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME"
MCP_ACA_JOBS_COSMOS_DATABASE="$MCP_ACA_JOBS_COSMOS_DATABASE"
MCP_ACA_JOBS_COSMOS_CONTAINER="$MCP_ACA_JOBS_COSMOS_CONTAINER"
MCP_AUTH_APP_CLIENT_ID="$MCP_AUTH_APP_CLIENT_ID"
MCP_ACA_JOBS_CALLER_PRINCIPAL_ID="$MCP_ACA_JOBS_CALLER_PRINCIPAL_ID"
MCP_ACA_JOBS_CALLER_CLIENT_ID="$AZURE_CLIENT_ID"
FOUNDRY_PROJECT_ENDPOINT="$FOUNDRY_PROJECT_ENDPOINT"
AZURE_AI_PROJECT_ID="$AZURE_AI_PROJECT_ID"
AZURE_AI_MODEL_DEPLOYMENT_NAME="$FOUNDRY_MODEL_DEPLOYMENT"
AZURE_CONTAINER_REGISTRY_ENDPOINT="$ACR_LOGIN_SERVER"
SERVICE_MCP_IMAGE_NAME="$ACR_LOGIN_SERVER/ci-smoke-mcp-jobs-$SUFFIX:run"
EOF

(
  cd "$PROJECT_DIR"
  uv sync --frozen --group fixture
) || fail "uv sync failed"

## Step 3 — provider and build verification

provider_json="$(az provider operation show --namespace Microsoft.App --output json)"
for action in \
  Microsoft.App/jobs/read \
  Microsoft.App/jobs/start/action \
  Microsoft.App/jobs/execution/read \
  Microsoft.App/jobs/executions/read \
  Microsoft.App/jobs/stop/execution/action
do
  jq -e --arg action "$action" \
    '.. | objects | .name? | select(type == "string") |
     select(ascii_downcase == ($action | ascii_downcase))' \
    <<<"$provider_json" >/dev/null ||
    fail "Microsoft.App provider action missing: $action"
done
echo RBAC_PROVIDER_ACTIONS_MATCH

azd ext install microsoft.foundry ||
  fail "microsoft.foundry extension install failed"
azd ext install azure.ai.agents --version 1.0.0-beta.14 --force ||
  fail "supported hosted consumer install failed"
extensions_json="$(azd ext list --output json)"
jq -e \
  '[.[] | select(.id == "microsoft.foundry") | .installedVersion |
    select(type == "string" and length > 0)] | length == 1' \
  <<<"$extensions_json" >/dev/null ||
  fail "microsoft.foundry extension not installed"
jq -e \
  '[.[] | select(.id == "azure.ai.agents") | .installedVersion |
    select(type == "string" and length > 0)] | length == 1' \
  <<<"$extensions_json" >/dev/null ||
  fail "azure.ai.agents extension not installed"

(
  cd "$PROJECT_DIR"
  AZURE_ENV_NAME="$AZD_ENV_NAME" azd up --no-prompt
) > "$SCRATCH_ROOT/azd-up.log" 2>&1 || {
  tail -n 60 "$SCRATCH_ROOT/azd-up.log" | redact >> "$EVIDENCE"
  fail "azd up failed"
}
python3 "$PROJECT_DIR/infra/scripts/ci_reuse.py" record-image \
  --project "$PROJECT_DIR" || fail "exact run image not recorded"

MCP_FQDN="$(az containerapp show \
  --resource-group "$CHILD_RG" \
  --name "$APP_NAME" \
  --query properties.configuration.ingress.fqdn \
  --output tsv)"
test -n "$MCP_FQDN" || fail "MCP app FQDN missing"
MCP_URL="https://$MCP_FQDN/mcp"
export MCP_URL

EXPECTED_IMAGE_DIGEST="$(az containerapp show \
  --resource-group "$CHILD_RG" \
  --name "$APP_NAME" \
  --query 'properties.template.containers[0].image' \
  --output tsv)"
[[ "$EXPECTED_IMAGE_DIGEST" == "$ACR_LOGIN_SERVER/"*"@sha256:"* ]] ||
  fail "app image is not the expected immutable ACR digest"
export EXPECTED_IMAGE_DIGEST
verifier_output="$(
  cd "$PROJECT_DIR/infra/scripts"
  AZURE_ENV_NAME="$AZD_ENV_NAME" uv run --frozen python verify_deployment.py
)" || fail "shared digest or entrypoint verification failed"
printf '%s\n' "$verifier_output"
grep -Fxq "SHARED_IMAGE_DIGEST_MATCH" <<<"$verifier_output" ||
 fail "shared image digest verifier marker missing"
grep -Fxq "ENTRYPOINTS_MATCH" <<<"$verifier_output" ||
 fail "entrypoint verifier marker missing"

## Step 4 — task-aware and fallback client smoke

export CALLBACK_CONTAINER_URL="${MCP_ACA_JOBS_STORAGE_ACCOUNT_URL%/}/${MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME}-callbacks"
(
cd "$PROJECT_DIR"
uv run --frozen --group fixture python - <<'PY'
import asyncio
import json
import os
from urllib.parse import urlsplit

from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobClient
from fastmcp import Client
from fastmcp_tasks.client import TasksClientExtension
from fastmcp_tasks.client import call_tool_task

CALLBACK_FIELDS = {"taskId", "acaExecutionId", "status", "resultUrl"}
TERMINAL = {"Succeeded", "Failed", "Cancelled"}


def dump(value):
    return value.model_dump(mode="json", by_alias=True) if hasattr(value, "model_dump") else value


def payload(result):
    for candidate in (
        getattr(result, "data", None),
        getattr(result, "structured_content", None),
        dump(result),
    ):
        candidate = dump(candidate)
        if isinstance(candidate, dict):
            for key in ("structuredContent", "structured_content", "data"):
                if isinstance(candidate.get(key), dict):
                    return candidate[key]
            return candidate
    raise AssertionError("tool result has no structured object")


def result_url(value, storage_host, *, callback=False):
    assert set(value) == ({"status", "resultUrl"} if callback else {"status", "resultUrl", "effectState"})
    if not callback:
        assert value["effectState"] == "UNKNOWN"
    assert value["status"] == "Succeeded"
    parsed = urlsplit(value["resultUrl"])
    assert parsed.scheme == "https" and parsed.hostname == storage_host
    assert not parsed.username and not parsed.password
    assert not parsed.query and not parsed.fragment
    return value["resultUrl"]


async def main():
    credential = DefaultAzureCredential()
    storage_url = os.environ["MCP_ACA_JOBS_STORAGE_ACCOUNT_URL"].rstrip("/")
    output_container = os.environ["MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME"]
    input_ref = f"{storage_url}/{output_container}/inputs/{os.environ['SUFFIX']}.json"
    input_blob = BlobClient.from_blob_url(input_ref, credential=credential)
    await input_blob.upload_blob(b'{"durationSeconds":2}', overwrite=True)
    await input_blob.close()
    agent_input_refs = (
        f"{storage_url}/{output_container}/inputs/PROMPT_AGENT_MCP_PASS-"
        f"{os.environ['SUFFIX']}.json",
        f"{storage_url}/{output_container}/inputs/HOSTED_AGENT_MCP_PASS-"
        f"{os.environ['SUFFIX']}.json",
    )
    for agent_input_ref in agent_input_refs:
        agent_input_blob = BlobClient.from_blob_url(
            agent_input_ref, credential=credential
        )
        await agent_input_blob.upload_blob(
            b'{"durationSeconds":2}', overwrite=True
        )
        await agent_input_blob.close()

    access_token = (
        await credential.get_token(f"api://{os.environ['MCP_AUTH_APP_CLIENT_ID']}/.default")
    ).token
    request = {
        "jobType": "short-job",
        "idempotencyKey": f"direct-{os.environ['SUFFIX']}",
        "inputRef": input_ref,
        "callbackAlias": "ops",
    }
    async with Client(
        os.environ["MCP_URL"],
        extensions=[TasksClientExtension()],
        auth=access_token,
        timeout=90,
    ) as client:
        task = await call_tool_task(client, "start_aca_job", request, timeout=90)
        terminal = await task.wait(timeout=600)
        assert dump(terminal)["status"] == "completed"
        direct = payload(await task.result())
        direct_url = result_url(
            direct, urlsplit(storage_url).hostname or ""
        )

        duplicate = await call_tool_task(client, "start_aca_job", request, timeout=90)
        duplicate_terminal = await duplicate.wait(timeout=120)
        assert dump(duplicate_terminal)["status"] == "completed"
        duplicate_result = payload(await duplicate.result())
        assert duplicate.task_id == task.task_id
        assert duplicate_result == direct
        assert duplicate_result["resultUrl"] == direct_url

        cancel_request = dict(request)
        cancel_request["idempotencyKey"] = f"cancel-{os.environ['SUFFIX']}"
        cancel_task = await call_tool_task(
            client, "start_aca_job", cancel_request, timeout=90
        )
        await cancel_task.cancel()
        cancel_terminal = await cancel_task.wait(timeout=300)
        assert dump(cancel_terminal)["status"] in {"cancelled", "completed"}

    fallback = dict(request)
    fallback["idempotencyKey"] = f"fallback-{os.environ['SUFFIX']}"
    async with Client(
        os.environ["MCP_URL"],
        mode="legacy",
        extensions=[],
        auth=access_token,
        timeout=90,
    ) as client:
        started = payload(await client.call_tool("start_aca_job", fallback))
        assert "resultType" not in started
        fallback_id = started["taskId"]
        status = payload(
            await client.call_tool("get_aca_job_status", {"taskId": fallback_id})
        )
        assert status["taskId"] == fallback_id and "resultType" not in status
        cancelled = payload(
            await client.call_tool("cancel_aca_job", {"taskId": fallback_id})
        )
        assert cancelled["taskId"] == fallback_id and "resultType" not in cancelled
        for _ in range(30):
            if cancelled["status"] in TERMINAL:
                break
            await asyncio.sleep(5)
            cancelled = payload(
                await client.call_tool("get_aca_job_status", {"taskId": fallback_id})
            )
        assert cancelled["status"] in TERMINAL

    callback_url = (
        f"{os.environ['CALLBACK_CONTAINER_URL']}/callbacks/{task.task_id}.json"
    )
    callback_blob = BlobClient.from_blob_url(callback_url, credential=credential)
    try:
        for _ in range(60):
            try:
                callback = json.loads(await (await callback_blob.download_blob()).readall())
                break
            except ResourceNotFoundError:
                await asyncio.sleep(5)
        else:
            raise TimeoutError("callback did not arrive in 300 seconds")
    finally:
        await callback_blob.close()
    assert set(callback) == CALLBACK_FIELDS
    assert callback["taskId"] == task.task_id
    assert callback["acaExecutionId"]
    assert result_url(
        {"status": callback["status"], "resultUrl": callback["resultUrl"]},
        urlsplit(storage_url).hostname or "",
        callback=True,
    ) == direct_url
    await credential.close()

    print("MCP_TASKS_COMPLETED")
    print("FALLBACK_TOOLS_COMPLETED")
    print("IDEMPOTENCY_DUPLICATE_SAME_TASK")
    print("CALLBACK_PAYLOAD_VALID")
    print("CANCELLATION_TERMINAL")


asyncio.run(main())
PY
) 2>&1 | redact | tee -a "$EVIDENCE"

## Step 5 — prompt agent smoke

# Agent grading: the closed start/status shapes never echo inputRef, so the
# marker is proven through the worker's result for the chained taskId.
cat > "$PROJECT_DIR/ci_agent_check.py" <<'PY'
import json
import os
import time

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobClient


def first_json_object(output):
    # Foundry may append further content blocks after the tool's JSON object.
    value, _ = json.JSONDecoder().raw_decode((output or "{}").lstrip())
    assert isinstance(value, dict), "MCP output is not a JSON object"
    return value


def verify_agent_calls(calls_by_name, marker, credential):
    for item in calls_by_name.values():
        assert getattr(item, "error", None) in (None, ""), "MCP call returned error"
    started = first_json_object(getattr(calls_by_name["start_aca_job"], "output", ""))
    status = first_json_object(getattr(calls_by_name["get_aca_job_status"], "output", ""))
    task_id = started.get("taskId")
    assert task_id and status.get("taskId") == task_id, "status call did not chain the start taskId"
    url = (
        f"{os.environ['MCP_ACA_JOBS_STORAGE_ACCOUNT_URL'].rstrip('/')}/"
        f"{os.environ['MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME']}/results/{task_id}/result.json"
    )
    blob = BlobClient.from_blob_url(url, credential=credential)
    try:
        for _ in range(60):
            try:
                result = json.loads(blob.download_blob().readall())
                break
            except ResourceNotFoundError:
                time.sleep(5)
        else:
            raise AssertionError("agent task produced no result in 300 seconds")
    finally:
        blob.close()
    assert result.get("taskId") == task_id, "result belongs to another task"
    assert marker in result.get("inputPath", ""), "agent task did not use the marker inputRef"
    return task_id
PY

(
cd "$PROJECT_DIR"
uv run --frozen --group fixture python - <<'PY'
import os
import re
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential
from infra.scripts.ci_reuse import invoke_once


def redact_error(value):
    value = re.sub(r"(?i)Bearer\s+\S+", "<redacted-bearer>", value)
    return re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", "<redacted-jwt>", value)


credential = DefaultAzureCredential()
project = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential
)
name = f"ci-mcp-jobs-prompt-{os.environ['SUFFIX']}"
version = None
try:
    access_token = credential.get_token(
        f"api://{os.environ['MCP_AUTH_APP_CLIENT_ID']}/.default"
    ).token
    version = project.agents.create_version(
        agent_name=name,
        definition=PromptAgentDefinition(
            model=os.environ["FOUNDRY_MODEL_DEPLOYMENT"],
            instructions=(
                "Call start_aca_job once, then get_aca_job_status with its taskId. "
                "Use the requested inputRef exactly. Do not emit the verification "
                "marker as assistant text."
            ),
            tools=[
                MCPTool(
                    server_label="aca_jobs",
                    server_url=os.environ["MCP_URL"],
                    # Static bearer is smoke-only; production must use project_connection_id.
                    # The service rejects sensitive Authorization values in headers.
                    authorization=access_token,
                    # Foundry opts in to MCP tasks but cannot consume a task handle.
                    headers={"X-MCP-Task-Mode": "inline"},
                    require_approval="never",
                )
            ],
        ),
    )
    openai = project.get_openai_client()
    conversation = openai.conversations.create()
    response = None
    last_error = None
    marker = "PROMPT_AGENT_MCP_PASS"
    try:
        response = invoke_once(openai, "prompt", {
            "conversation": conversation.id,
            "extra_body": {"agent_reference": {"name": name, "type": "agent_reference"}},
            "input": (
                "Call start_aca_job with jobType short-job, idempotencyKey "
                f"prompt-{os.environ['SUFFIX']}, inputRef "
                f"{os.environ['MCP_ACA_JOBS_STORAGE_ACCOUNT_URL'].rstrip('/')}/"
                f"{os.environ['MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME']}/inputs/"
                f"{marker}-{os.environ['SUFFIX']}.json, and callbackAlias ops. "
                "Then call get_aca_job_status with the returned taskId."
            ),
        })
    except Exception as exc:
        # Diagnostics only (no replay): the service error names the failing tool call.
        cause = exc.__context__ or exc
        print("PROMPT_INVOKE_ERROR", type(cause).__name__, redact_error(str(cause))[:800])
        try:
            for item in openai.conversations.items.list(conversation_id=conversation.id):
                if getattr(item, "type", "") in ("mcp_call",):
                    print("PROMPT_MCP_CALL", getattr(item, "name", None),
                          redact_error(str(getattr(item, "error", None)))[:400])
        except Exception as exc:
            print(f"NOTE conversation items unavailable: {type(exc).__name__}")
        raise
    last_error_repr = redact_error(repr(last_error))
    assert response is not None, f"invoke never succeeded: {last_error_repr}"
    calls = [
        item
        for item in response.output
        if getattr(item, "type", None) == "mcp_call"
    ]
    calls_by_name = {getattr(item, "name", None): item for item in calls}
    assert set(calls_by_name) == {
        "start_aca_job",
        "get_aca_job_status",
    }, f"required MCP calls missing; last_error={last_error_repr}"
    from ci_agent_check import verify_agent_calls
    verify_agent_calls(calls_by_name, marker, credential)
    print("PROMPT_AGENT_MCP_CALLS_VALID")
finally:
    if version is not None:
        try:
            project.agents.delete_version(name, str(version.version))
        except Exception as exc:
            print(f"NOTE prompt-agent delete best effort: {type(exc).__name__}")
    project.close()
    credential.close()
PY
) 2>&1 | redact | tee -a "$EVIDENCE"

## Step 6 — hosted agent smoke

HOSTED_DIR="$PROJECT_DIR/hosted-agent"
mkdir -p "$HOSTED_DIR"
cp skills/foundry-hosted-agents/references/docker/Dockerfile "$HOSTED_DIR/Dockerfile"
cp skills/foundry-hosted-agents/references/python/pyproject.toml "$HOSTED_DIR/pyproject.toml"
printf 'Use the ACA Jobs MCP tools exactly as instructed.\n' \
  > "$HOSTED_DIR/copilot-instructions.md"
cat > "$HOSTED_DIR/.dockerignore" <<'IGNORE'
**
!Dockerfile
!container.py
!pyproject.toml
!uv.lock
!copilot-instructions.md
IGNORE
cp "$HOSTED_DIR/.dockerignore" "$HOSTED_DIR/.azdignore"

cat > "$HOSTED_DIR/container.py" <<'PY'
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential


def main():
    token_credential = SyncDefaultAzureCredential()
    access_token = token_credential.get_token(
        os.environ["MCP_AUTH_AUDIENCE"]
    ).token
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=AsyncDefaultAzureCredential(),
    )
    mcp_tool = client.get_mcp_tool(
        name="ACA Jobs",
        url=os.environ["MCP_SERVER_URL"],
        # Static bearer is smoke-only; production must use a header provider.
        # Foundry opts in to MCP tasks but cannot consume a task handle (#488).
        headers={"Authorization": "Bearer " + access_token, "X-MCP-Task-Mode": "inline"},
        approval_mode="never_require",
    )
    agent = Agent(
        client=client,
        instructions=(
            "Call start_aca_job once, then get_aca_job_status with its taskId. "
            "Use the requested inputRef exactly. Do not emit the verification "
            "marker as assistant text."
        ),
        tools=[mcp_tool],
        default_options={"store": False},
    )
    ResponsesHostServer(agent).run()


if __name__ == "__main__":
    main()
PY

cat > "$HOSTED_DIR/azure.yaml" <<EOF
name: $HOSTED_NAME
requiredVersions:
  extensions:
    azure.ai.agents: '>=1.0.0-beta.4'
services:
  ai-project:
    host: azure.ai.project
    endpoint: \${FOUNDRY_PROJECT_ENDPOINT}
  $HOSTED_NAME:
    host: azure.ai.agent
    project: .
    language: docker
    docker:
      registry: $ACR_LOGIN_SERVER
      image: $HOSTED_NAME
      tag: run
    uses:
      - ai-project
    kind: hosted
    name: $HOSTED_NAME
    protocols:
      - protocol: responses
        version: 2.0.0
    environmentVariables:
      - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
        value: \${AZURE_AI_MODEL_DEPLOYMENT_NAME}
      - name: MCP_SERVER_URL
        value: \${MCP_SERVER_URL}
      - name: MCP_AUTH_AUDIENCE
        value: \${MCP_AUTH_AUDIENCE}
    container:
      resources:
        cpu: "1"
        memory: 2Gi
infra:
  provider: microsoft.foundry
EOF

cp -R "$PROJECT_DIR/.azure" "$HOSTED_DIR/.azure"
cat >> "$HOSTED_DIR/.azure/$AZD_ENV_NAME/.env" <<EOF
MCP_SERVER_URL="$MCP_URL"
MCP_AUTH_AUDIENCE="api://$MCP_AUTH_APP_CLIENT_ID/.default"
EOF
(
cd "$PROJECT_DIR"
uv run --frozen --group fixture python - <<'PY'
import os
from pathlib import Path
from azure.ai.projects import AIProjectClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from infra.scripts.ci_reuse import write_new

with DefaultAzureCredential() as credential, AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential,
    retry_total=0, connection_timeout=10, read_timeout=30,
) as project:
    try:
        project.agents.get(agent_name=os.environ["HOSTED_NAME"])
    except ResourceNotFoundError:
        write_new(Path("ci-hosted-intent.json"), {"name": os.environ["HOSTED_NAME"], "absent_before": True})
    else:
        raise RuntimeError("Hosted target already exists; do not adopt or delete it")
PY
) || fail "hosted ownership preflight failed"
HOSTED_DEPLOYED=false
for attempt in 1 2 3; do
  if (
    cd "$HOSTED_DIR"
    AZURE_ENV_NAME="$AZD_ENV_NAME" azd deploy "$HOSTED_NAME" --no-prompt
  ) 2>&1 | tee "$SCRATCH_ROOT/hosted-deploy-$attempt.log"; then
    HOSTED_DEPLOYED=true
    break
  fi
  # Only the transient publish 404 is retried; anything else fails at once.
  grep -Eq '\b404\b|NotFound|Not Found' "$SCRATCH_ROOT/hosted-deploy-$attempt.log" || break
  echo "NOTE hosted azd deploy attempt $attempt hit a transient 404; retrying"
  sleep 30
done
[[ "$HOSTED_DEPLOYED" == true ]] || fail "hosted agent deploy failed"
python3 "$PROJECT_DIR/infra/scripts/ci_reuse.py" record-image --hosted-image \
  --project "$PROJECT_DIR" || fail "hosted run image not recorded"

(
cd "$PROJECT_DIR"
uv run --frozen --group fixture python - <<'PY'
import os
import time
from pathlib import Path
from infra.scripts.ci_reuse import write_new

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


credential = DefaultAzureCredential()
project = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential
)
try:
    for _ in range(24):
        version = project.agents.get_version(
            agent_name=os.environ["HOSTED_NAME"], agent_version="1"
        )
        status = version.get("status") if isinstance(version, dict) else version.status
        if status == "active":
            assert version.name == os.environ["HOSTED_NAME"] and str(version.version) == "1"
            assert version.created_at is not None, "Missing native creation identity"
            write_new(Path("ci-hosted-owned.json"), {
                "name": os.environ["HOSTED_NAME"], "version": str(version.version),
                "created_at": str(version.created_at),
            })
            print("HOSTED_AGENT_ACTIVE")
            break
        if status == "failed":
            raise RuntimeError("hosted agent version failed")
        time.sleep(10)
    else:
        raise TimeoutError("hosted agent version did not become active")
finally:
    project.close()
    credential.close()
PY
) || fail "hosted agent did not become active"

HOSTED_PRINCIPAL_ID=""
HOSTED_CLIENT_ID=""
HOSTED_IDENTITY_LAST_ERROR="hosted agent principal ID was empty"
for attempt in $(seq 1 6); do
  HOSTED_IDENTITY_RESPONSE=""
  if HOSTED_IDENTITY_RESPONSE="$(
    az rest \
      --method get \
      --url "${FOUNDRY_PROJECT_ENDPOINT%/}/agents/${HOSTED_NAME}?api-version=v1" \
      --resource https://ai.azure.com \
      --output json 2>&1
  )"; then
    if HOSTED_PRINCIPAL_ID="$(
      jq -er '
        [
          .instance_identity.principal_id?,
          .versions.latest.instance_identity.principal_id?
        ]
        | map(select(type == "string" and length > 0))
        | first // empty
      ' <<<"$HOSTED_IDENTITY_RESPONSE"
    )"
    then
      # Easy Auth also checks the token azp; ACA denies an empty allowedApplications.
      HOSTED_CLIENT_ID="$(
        jq -er '
          [
            .instance_identity.client_id?,
            .versions.latest.instance_identity.client_id?
          ]
          | map(select(type == "string" and length > 0))
          | first // empty
        ' <<<"$HOSTED_IDENTITY_RESPONSE"
      )" && break
    fi
    HOSTED_IDENTITY_LAST_ERROR="hosted agent principal or client ID was empty in both supported response shapes"
  else
    HOSTED_IDENTITY_LAST_ERROR="$(
      printf '%s\n' "$HOSTED_IDENTITY_RESPONSE" | tail -n 1
    )"
    test -n "$HOSTED_IDENTITY_LAST_ERROR" ||
      HOSTED_IDENTITY_LAST_ERROR="az rest failed without a diagnostic"
  fi
  if [[ "$attempt" -lt 6 ]]; then
    sleep 10
  fi
done
test -n "$HOSTED_PRINCIPAL_ID" && test -n "${HOSTED_CLIENT_ID:-}" ||
  fail "hosted agent identity lookup failed after 6 attempts: $HOSTED_IDENTITY_LAST_ERROR"

AUTH_CONFIG_URL="https://management.azure.com/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${CHILD_RG}/providers/Microsoft.App/containerApps/${APP_NAME}/authConfigs/current?api-version=2025-01-01"
AUTH_CONFIG_PROPERTIES="$(
  az rest \
    --method get \
    --url "$AUTH_CONFIG_URL" \
    --query properties \
    --output json
)" || fail "Easy Auth configuration read failed"
UPDATED_AUTH_CONFIG_BODY="$(
  jq -c --arg principal_id "$HOSTED_PRINCIPAL_ID" --arg client_id "$HOSTED_CLIENT_ID" '
    (.identityProviders //= {})
    | (.identityProviders.azureActiveDirectory //= {})
    | (.identityProviders.azureActiveDirectory.validation //= {})
    | (.identityProviders.azureActiveDirectory.validation
        .defaultAuthorizationPolicy //= {})
    | (.identityProviders.azureActiveDirectory.validation
        .defaultAuthorizationPolicy.allowedApplications //= [])
    | if (.identityProviders.azureActiveDirectory.validation
        .defaultAuthorizationPolicy.allowedApplications
        | index($client_id)) == null
      then .identityProviders.azureActiveDirectory.validation
        .defaultAuthorizationPolicy.allowedApplications += [$client_id]
      else .
      end
    | (.identityProviders.azureActiveDirectory.validation
        .defaultAuthorizationPolicy.allowedPrincipals //= {})
    | (.identityProviders.azureActiveDirectory.validation
        .defaultAuthorizationPolicy.allowedPrincipals.identities //= [])
    | if (.identityProviders.azureActiveDirectory.validation
        .defaultAuthorizationPolicy.allowedPrincipals.identities
        | index($principal_id)) == null
      then .identityProviders.azureActiveDirectory.validation
        .defaultAuthorizationPolicy.allowedPrincipals.identities += [$principal_id]
      else .
      end
    | {properties: .}
  ' <<<"$AUTH_CONFIG_PROPERTIES"
)" || fail "Easy Auth caller allowlist update construction failed"
az rest \
  --method put \
  --url "$AUTH_CONFIG_URL" \
  --headers "Content-Type=application/json" \
  --body "$UPDATED_AUTH_CONFIG_BODY" \
  --output none ||
  fail "Easy Auth allowed principal identities update failed"

AUTH_ALLOWLIST_CONVERGED=false
for attempt in $(seq 1 12); do
  CURRENT_AUTHORIZATION_POLICY="$(
    az rest \
      --method get \
      --url "$AUTH_CONFIG_URL" \
      --query properties.identityProviders.azureActiveDirectory.validation.defaultAuthorizationPolicy \
      --output json
  )" || fail "Easy Auth allowed principal identities propagation poll failed"
  if jq -e --arg principal_id "$HOSTED_PRINCIPAL_ID" --arg client_id "$HOSTED_CLIENT_ID" \
    '((.allowedApplications // []) | index($client_id) != null) and
     ((.allowedPrincipals.identities // []) | index($principal_id) != null)' \
    <<<"$CURRENT_AUTHORIZATION_POLICY" >/dev/null
  then
    AUTH_ALLOWLIST_CONVERGED=true
    break
  fi
  if [[ "$attempt" -lt 12 ]]; then
    sleep 5
  fi
done
[[ "$AUTH_ALLOWLIST_CONVERGED" == true ]] ||
  fail "hosted agent client or principal ID missing from the Easy Auth caller allowlist after bounded poll"

ACTIVE_REVISIONS=""
for attempt in $(seq 1 6); do
  if ACTIVE_REVISIONS="$(
    az containerapp revision list \
      --resource-group "$CHILD_RG" \
      --name "$APP_NAME" \
      --query "[?properties.active].name" \
      --output tsv
  )" && [[ -n "$ACTIVE_REVISIONS" ]]
  then
    break
  fi
  if [[ "$attempt" -lt 6 ]]; then
    sleep 5
  fi
done
test -n "$ACTIVE_REVISIONS" ||
  fail "active Container App revision lookup failed after 6 attempts"
while IFS= read -r revision; do
  test -n "$revision" || continue
  REVISION_RESTARTED=false
  for attempt in $(seq 1 6); do
    if az containerapp revision restart --resource-group "$CHILD_RG" --name "$APP_NAME" --revision "$revision"
    then
      REVISION_RESTARTED=true
      break
    fi
    if [[ "$attempt" -lt 6 ]]; then
      sleep 5
    fi
  done
  [[ "$REVISION_RESTARTED" == true ]] ||
    fail "active Container App revision restart failed after 6 attempts"
done <<<"$ACTIVE_REVISIONS"

(
cd "$PROJECT_DIR"
uv run --frozen --group fixture python - <<'PY'
import os
import re
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentEndpointConfig,
    FixedRatioVersionSelectionRule,
    ProtocolConfiguration,
    ResponsesProtocolConfiguration,
    VersionSelector,
)
from azure.identity import DefaultAzureCredential


def redact_error(value):
    value = re.sub(r"(?i)Bearer\s+\S+", "<redacted-bearer>", value)
    return re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", "<redacted-jwt>", value)


credential = DefaultAzureCredential()
project = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential
)
name = os.environ["HOSTED_NAME"]
from infra.scripts.ci_reuse import invoke_once

project.agents.update_details(
    agent_name=name,
    agent_endpoint=AgentEndpointConfig(
        version_selector=VersionSelector(
            version_selection_rules=[
                FixedRatioVersionSelectionRule(
                    agent_version="1", traffic_percentage=100
                )
            ]
        ),
        protocol_configuration=ProtocolConfiguration(
            responses=ResponsesProtocolConfiguration()
        ),
    ),
)
openai = project.get_openai_client(agent_name=name)
response = None
last_error = None
marker = "HOSTED_AGENT_MCP_PASS"
response = invoke_once(openai, "hosted", {
    "input": (
        "Call start_aca_job with jobType short-job, idempotencyKey "
        f"hosted-{os.environ['SUFFIX']}, inputRef "
        f"{os.environ['MCP_ACA_JOBS_STORAGE_ACCOUNT_URL'].rstrip('/')}/"
        f"{os.environ['MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME']}/inputs/"
        f"{marker}-{os.environ['SUFFIX']}.json, and callbackAlias ops. "
        "Then call get_aca_job_status with the returned taskId."
    ),
    "stream": False,
})
last_error_repr = redact_error(repr(last_error))
assert response is not None, f"invoke never succeeded: {last_error_repr}"
calls = [
    item
    for item in response.output
    if getattr(item, "type", None) == "mcp_call"
]
calls_by_name = {getattr(item, "name", None): item for item in calls}
assert set(calls_by_name) == {
    "start_aca_job",
    "get_aca_job_status",
}, f"required MCP calls missing; last_error={last_error_repr}"
from ci_agent_check import verify_agent_calls
verify_agent_calls(calls_by_name, marker, credential)
project.close()
credential.close()
print("HOSTED_AGENT_MCP_CALLS_VALID")
PY
) 2>&1 | redact | tee -a "$EVIDENCE"

## Step 7 — targeted run-owned cleanup

# Only the exact five ARM objects with recorded pre-write absence and matching
# creation observations are cleanup candidates. This NEVER deletes the standing
# database/account/storage/identity/RG/grants. The current live approval must
# cover their deletion. An unverified residual is a cleanup blocker, not PASS.
python3 "$PROJECT_DIR/infra/scripts/ci_reuse.py" cleanup \
  --project "$PROJECT_DIR" --execute || fail "run-owned cleanup incomplete"

(
cd "$PROJECT_DIR"
uv run --frozen --group fixture python - <<'PY'
import os

from azure.ai.projects import AIProjectClient
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential

with DefaultAzureCredential() as credential, AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential,
    retry_total=0, connection_timeout=10, read_timeout=30,
) as project:
    from pathlib import Path
    from infra.scripts.ci_reuse import load, write_new
    intent = load(Path("ci-hosted-intent.json"))
    owned = load(Path("ci-hosted-owned.json"))
    assert intent == {"name": os.environ["HOSTED_NAME"], "absent_before": True}
    assert owned["name"] == intent["name"]
    import time
    from azure.core.exceptions import HttpResponseError
    version = project.agents.get_version(agent_name=owned["name"], agent_version=owned["version"])
    assert str(version.created_at) == owned["created_at"], "Hosted resource was replaced"
    # The agent was absent before this run, so the whole agent is run-owned.
    # Deleting it with force=True terminates active sessions; deleting only the
    # version fails while a session is active (#488). Bounded: 6 x 20 s, 12 x 10 s.
    absent = False
    for attempt in range(6):
        try:
            project.agents.delete(agent_name=owned["name"], force=True)
        except ResourceNotFoundError:
            pass
        except HttpResponseError as error:
            status = error.status_code or 0
            if status not in (409, 429) and status < 500:
                raise
            print(f"NOTE hosted delete attempt {attempt + 1} deferred: HTTP {status}")
            time.sleep(20)
            continue
        for _ in range(12):
            try:
                project.agents.get(agent_name=owned["name"])
            except ResourceNotFoundError:
                absent = True
                break
            time.sleep(10)
        if absent:
            break
    if not absent:
        raise RuntimeError("Owned hosted agent still present; cleanup incomplete")
    write_new(Path("ci-hosted-deleted.json"), {"name": owned["name"], "version": owned["version"], "absent": True})
    print("HOSTED_AGENT_ABSENCE_VERIFIED")
PY
) || fail "hosted-agent cleanup not verified"

# Preserve ci-run-owned.json/ci-created.json and all original operation receipts.
# Native hosted agent and the exact ACR image digest require their own recorded
# create provenance and absence verification; do not delete shared repositories
# or reconstruct logs by redeploying. Report retained image/agent residuals to
# the owner; require explicit bounded retention before declaring lifecycle done.
python3 "$PROJECT_DIR/infra/scripts/ci_reuse.py" cleanup-image \
  --project "$PROJECT_DIR" --execute || fail "run image cleanup not verified"
python3 "$PROJECT_DIR/infra/scripts/ci_reuse.py" cleanup-image --hosted-image \
  --project "$PROJECT_DIR" --execute || fail "hosted image cleanup not verified"
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-mcp-aca-jobs-smoke-result
echo "CI_REUSE_RESOURCE_CLEANUP_VERIFIED"

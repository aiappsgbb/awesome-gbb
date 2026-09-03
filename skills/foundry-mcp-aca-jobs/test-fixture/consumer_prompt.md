# Customer goal — `foundry-mcp-aca-jobs` skill smoke

Execute this live Azure smoke exactly as written. Do not replace commands,
invent fallback implementations, or browse the repository.

## Step -1 — acknowledge the skill contract

Your first Bash action must be:

```bash
echo "skills/foundry-mcp-aca-jobs/SKILL.md"
```

Do NOT browse the repository. Do not view, glob, grep, or search files.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You are
already the running Copilot CLI process. Execute the commands below directly.

## Step 0 — auth context and deterministic failure contract

The workflow has installed `az`, `azd`, `uv`, `curl`, `jq`, `python3`, and
`uuidgen`. Never install tools or search for binaries. CI grades only
`/tmp/foundry-mcp-aca-jobs-smoke-result`, not assistant prose.

Run every remaining step in one Bash action using the exact block below.
The `ERR` trap writes a deterministic FAIL marker for any unhandled hard
abort; explicit preconditions write a more precise FAIL marker.

```bash
set -Eeuo pipefail
MARKER=/tmp/foundry-mcp-aca-jobs-smoke-result
rm -f "$MARKER"

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
PROJECT_DIR="$GITHUB_WORKSPACE/.scratch/ci-smoke-mcp-jobs-$SUFFIX"
CHILD_RG="rg-foundry-mcp-aca-jobs-ci-$SUFFIX"
AZD_ENV_NAME="ci-smoke-mcp-jobs-$SUFFIX"
APP_NAME="ci-smoke-mcp-jobs-$SUFFIX"
JOB_NAME="ci-smoke-mcp-jobs-worker-$SUFFIX"
HOSTED_NAME="ci-smoke-mcp-jobs-hosted-$SUFFIX"
ACR_NAME="${ACR_LOGIN_SERVER%%.*}"
MCP_ACA_JOBS_PLATFORM_RESOURCE_GROUP="rg-awesome-gbb-ci"
MCP_ACA_JOBS_ENVIRONMENT_NAME="cae-awesome-gbb-ci"
MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME="mcpjobs-$SUFFIX"
MCP_ACA_JOBS_COSMOS_DATABASE="ci-smoke-mcp-jobs-db-$SUFFIX"
MCP_ACA_JOBS_COSMOS_CONTAINER="ci-smoke-mcp-jobs-task-$SUFFIX"
MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME="$(
  python3 -c 'import os,urllib.parse; print((urllib.parse.urlsplit(os.environ["MCP_ACA_JOBS_STORAGE_ACCOUNT_URL"]).hostname or "").split(".")[0])'
)"
MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME="$(
  python3 -c 'import os,urllib.parse; print((urllib.parse.urlsplit(os.environ["MCP_ACA_JOBS_COSMOS_ENDPOINT"]).hostname or "").split(".")[0])'
)"
export SUFFIX PROJECT_DIR CHILD_RG AZD_ENV_NAME APP_NAME JOB_NAME HOSTED_NAME
export ACR_NAME MCP_ACA_JOBS_PLATFORM_RESOURCE_GROUP
export MCP_ACA_JOBS_ENVIRONMENT_NAME MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME
export MCP_ACA_JOBS_COSMOS_DATABASE MCP_ACA_JOBS_COSMOS_CONTAINER
export MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME

[[ "$PROJECT_DIR" == "$GITHUB_WORKSPACE/.scratch/"* ]] ||
  fail "scratch workspace escaped GITHUB_WORKSPACE/.scratch"
[[ "$CHILD_RG" == rg-foundry-mcp-aca-jobs-ci-* ]] ||
  fail "child resource group name is invalid"

az group create --name "$CHILD_RG" \
  --location swedencentral \
  --tags cleanup=true created-by=ci-smoke \
  --only-show-errors >/dev/null ||
  fail "child resource group creation failed"

## Step 2 — deterministic scaffold

mkdir -p "$PROJECT_DIR"
cp skills/foundry-mcp-aca-jobs/templates/azure.yaml "$PROJECT_DIR/azure.yaml"
cp skills/foundry-mcp-aca-jobs/templates/Dockerfile "$PROJECT_DIR/Dockerfile"
cp skills/foundry-mcp-aca-jobs/templates/pyproject.toml "$PROJECT_DIR/pyproject.toml"
cp skills/foundry-mcp-aca-jobs/templates/uv.lock "$PROJECT_DIR/uv.lock"
cp -R skills/foundry-mcp-aca-jobs/templates/infra "$PROJECT_DIR/infra"
cp -R skills/foundry-mcp-aca-jobs/references/python/app "$PROJECT_DIR/app"
mkdir -p "$PROJECT_DIR/.azure/$AZD_ENV_NAME"

python3 - "$PROJECT_DIR/infra/main.parameters.json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
document = json.loads(path.read_text(encoding="utf-8"))
document["parameters"]["cosmosUseExistingAccount"]["value"] = True
path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
PY

cat > "$PROJECT_DIR/.azure/config.json" <<EOF
{"defaultEnvironment":"$AZD_ENV_NAME"}
EOF
cat > "$PROJECT_DIR/.azure/$AZD_ENV_NAME/.env" <<EOF
AZURE_ENV_NAME="$AZD_ENV_NAME"
AZURE_LOCATION="swedencentral"
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
MCP_APP_NAME="$APP_NAME"
ACA_JOB_NAME="$JOB_NAME"
MCP_ACA_JOBS_STORAGE_ACCOUNT_URL="${MCP_ACA_JOBS_STORAGE_ACCOUNT_URL%/}"
MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME="$MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME"
MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME="$MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME"
MCP_ACA_JOBS_COSMOS_ENDPOINT="${MCP_ACA_JOBS_COSMOS_ENDPOINT%/}"
MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME="$MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME"
MCP_ACA_JOBS_COSMOS_DATABASE="$MCP_ACA_JOBS_COSMOS_DATABASE"
MCP_ACA_JOBS_COSMOS_CONTAINER="$MCP_ACA_JOBS_COSMOS_CONTAINER"
MCP_ACA_JOBS_COSMOS_USE_EXISTING_ACCOUNT="true"
MCP_AUTH_APP_CLIENT_ID="$MCP_AUTH_APP_CLIENT_ID"
FOUNDRY_PROJECT_ENDPOINT="$FOUNDRY_PROJECT_ENDPOINT"
AZURE_AI_PROJECT_ID="$AZURE_AI_PROJECT_ID"
AZURE_AI_MODEL_DEPLOYMENT_NAME="$FOUNDRY_MODEL_DEPLOYMENT"
AZURE_CONTAINER_REGISTRY_ENDPOINT="$ACR_LOGIN_SERVER"
SERVICE_MCP_IMAGE_NAME="$ACR_LOGIN_SERVER/mcp/service:ci-smoke-$SUFFIX"
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
    '.. | objects | .name? // empty | select(. == $action)' \
    <<<"$provider_json" >/dev/null ||
    fail "Microsoft.App provider action missing: $action"
done
echo RBAC_PROVIDER_ACTIONS_MATCH

azd ext install microsoft.foundry ||
  fail "microsoft.foundry extension install failed"
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
) || fail "azd up failed"

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
(
  cd "$PROJECT_DIR/infra/scripts"
  AZURE_ENV_NAME="$AZD_ENV_NAME" uv run --frozen python verify_deployment.py
) || fail "shared digest or entrypoint verification failed"
# The canonical verifier must emit SHARED_IMAGE_DIGEST_MATCH and
# ENTRYPOINTS_MATCH after asserting the exact app/job digest and commands.

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


def result_url(value, storage_host):
    assert set(value) == {"status", "resultUrl"}
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
    ) == direct_url
    await credential.close()

    print("MCP_TASKS_COMPLETED")
    print("FALLBACK_TOOLS_COMPLETED")
    print("IDEMPOTENCY_DUPLICATE_SAME_TASK")
    print("CALLBACK_PAYLOAD_VALID")
    print("CANCELLATION_TERMINAL")


asyncio.run(main())
PY
)

## Step 5 — prompt agent smoke

(
cd "$PROJECT_DIR"
uv run --frozen --group fixture python - <<'PY'
import json
import os
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential


def text(value):
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json()
    return json.dumps(value, default=str)


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
                "Emit PROMPT_AGENT_MCP_PASS only after both calls."
            ),
            tools=[
                MCPTool(
                    server_label="aca_jobs",
                    server_url=os.environ["MCP_URL"],
                    headers={"Authorization": "Bearer " + access_token},
                    require_approval="never",
                )
            ],
        ),
    )
    openai = project.get_openai_client()
    conversation = openai.conversations.create()
    response = None
    for _ in range(12):
        try:
            response = openai.responses.create(
                conversation=conversation.id,
                extra_body={
                    "agent_reference": {"name": name, "type": "agent_reference"}
                },
                input=(
                    "Call start_aca_job with jobType short-job, idempotencyKey "
                    f"prompt-{os.environ['SUFFIX']}, inputRef "
                    f"{os.environ['MCP_ACA_JOBS_STORAGE_ACCOUNT_URL'].rstrip('/')}/"
                    f"{os.environ['MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME']}/inputs/"
                    f"{os.environ['SUFFIX']}.json, and callbackAlias ops. Then call "
                    "get_aca_job_status with the returned taskId and finish with "
                    "PROMPT_AGENT_MCP_PASS."
                ),
            )
            break
        except Exception:
            time.sleep(10)
    assert response is not None
    evidence = text(response)
    assert "start_aca_job" in evidence
    assert "get_aca_job_status" in evidence
    assert "PROMPT_AGENT_MCP_PASS" in evidence
    print("PROMPT_AGENT_MCP_PASS")
finally:
    if version is not None:
        try:
            project.agents.delete_version(name, str(version.version))
        except Exception as exc:
            print(f"NOTE prompt-agent delete best effort: {type(exc).__name__}")
    project.close()
    credential.close()
PY
)

## Step 6 — hosted agent smoke

HOSTED_DIR="$PROJECT_DIR/hosted-agent"
mkdir -p "$HOSTED_DIR"
cp skills/foundry-hosted-agents/references/docker/Dockerfile "$HOSTED_DIR/Dockerfile"
cp skills/foundry-hosted-agents/references/python/pyproject.toml "$HOSTED_DIR/pyproject.toml"
printf 'Use the ACA Jobs MCP tools exactly as instructed.\n' \
  > "$HOSTED_DIR/copilot-instructions.md"

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
        headers={"Authorization": "Bearer " + access_token},
        approval_mode="never_require",
    )
    agent = Agent(
        client=client,
        instructions=(
            "Call start_aca_job once, then get_aca_job_status with its taskId. "
            "Emit HOSTED_AGENT_MCP_PASS only after both calls."
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
  cd "$HOSTED_DIR"
  AZURE_ENV_NAME="$AZD_ENV_NAME" azd deploy "$HOSTED_NAME" --no-prompt
) || fail "hosted agent deploy failed"

(
cd "$PROJECT_DIR"
uv run --frozen --group fixture python - <<'PY'
import json
import os
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


credential = DefaultAzureCredential()
project = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential
)
name = os.environ["HOSTED_NAME"]
version = None
for _ in range(24):
    version = project.agents.get_version(agent_name=name, agent_version="1")
    status = version.get("status") if isinstance(version, dict) else version.status
    if status == "active":
        break
    if status == "failed":
        raise RuntimeError("hosted agent version failed")
    time.sleep(10)
else:
    raise TimeoutError("hosted agent version did not become active")

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
for _ in range(12):
    try:
        response = openai.responses.create(
            input=(
                "Call start_aca_job with jobType short-job, idempotencyKey "
                f"hosted-{os.environ['SUFFIX']}, inputRef "
                f"{os.environ['MCP_ACA_JOBS_STORAGE_ACCOUNT_URL'].rstrip('/')}/"
                f"{os.environ['MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME']}/inputs/"
                f"{os.environ['SUFFIX']}.json, and callbackAlias ops. Then call "
                "get_aca_job_status with the returned taskId and finish with "
                "HOSTED_AGENT_MCP_PASS."
            ),
            stream=False,
        )
        break
    except Exception:
        time.sleep(10)
assert response is not None
evidence = (
    response.model_dump_json()
    if hasattr(response, "model_dump_json")
    else json.dumps(response, default=str)
)
assert "start_aca_job" in evidence
assert "get_aca_job_status" in evidence
assert "HOSTED_AGENT_MCP_PASS" in evidence
project.close()
credential.close()
print("HOSTED_AGENT_MCP_PASS")
PY
)

## Step 7 — marker-first teardown

printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-mcp-aca-jobs-smoke-result
trap - ERR
set +e

# Five-minute best-effort targeted cleanup. The PASS marker is authoritative.
timeout 300 bash -c '
  az group delete --name "$CHILD_RG" --yes --no-wait
  az cosmosdb sql database delete \
    --resource-group "$MCP_ACA_JOBS_PLATFORM_RESOURCE_GROUP" \
    --account-name "$MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME" \
    --name "$MCP_ACA_JOBS_COSMOS_DATABASE" --yes
  for container in \
    "$MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME" \
    "$MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME-callbacks"
  do
    az storage container delete \
      --account-name "$MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME" \
      --name "$container" --auth-mode login
  done
  az acr repository delete --name "$ACR_NAME" \
    --image "mcp/service:ci-smoke-$SUFFIX" --yes
' || echo "NOTE best-effort Azure cleanup incomplete; PASS marker retained"

(
cd "$PROJECT_DIR"
uv run --frozen --group fixture python - <<'PY'
import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

try:
    credential = DefaultAzureCredential()
    project = AIProjectClient(
        endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential
    )
    project.agents.delete(agent_name=os.environ["HOSTED_NAME"], force=True)
    project.close()
    credential.close()
except Exception as exc:
    print(f"NOTE hosted-agent delete best effort: {type(exc).__name__}")
PY
) || true

rm -rf "$PROJECT_DIR"
echo "CLEANUP_BEST_EFFORT_COMPLETE"
```

No repository writes outside `.scratch/`. The brownfield Cosmos
CI mode creates only the UUID database/container in the standing account.
The callback payload must contain the exact four fields shown in Step 4.
PASS is written before best-effort targeted cleanup, and cleanup failure must
never replace it.

# Customer goal — `foundry-mcp-aca-jobs` skill smoke

You are a developer on a customer team. You installed the `awesome-gbb` Copilot CLI plugin and want to prove that the `foundry-mcp-aca-jobs` skill works end-to-end against the CI Foundry project.

Do whatever the skill tells you to do. Read the skill’s `SKILL.md` first, but do not browse the repository or improvise from training-data memory. This is an execution smoke, not a catalog inspection.

**CRITICAL — execution smoke, no repo browsing.** Do NOT browse the repository. Do NOT view files, glob, grep, or search for fixes. The first Bash action must be `echo "skills/foundry-mcp-aca-jobs/SKILL.md"`.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You are the running Copilot CLI process. Do not run `copilot -p`, `copilot --version`, `npm install -g @github/copilot`, or any other `copilot ...` invocation from inside Bash. The workflow already captures your output; your job is to execute the smoke steps directly.

---

## Step -1 — acknowledge the skill contract

Your first Bash action must be:

```bash
echo "skills/foundry-mcp-aca-jobs/SKILL.md"
```

Do not open any other repository file.

---

## Step 0 — auth context (show, do not assert)

Print the auth context for the run log. Hard-fail if any required value is missing. Do not compare subscription IDs, decode tokens, or gate on Azure CLI cache visibility.

```bash
set -Eeuo pipefail
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

: "${AZURE_CLIENT_ID:?missing AZURE_CLIENT_ID}"
: "${AZURE_TENANT_ID:?missing AZURE_TENANT_ID}"
: "${AZURE_SUBSCRIPTION_ID:?missing AZURE_SUBSCRIPTION_ID}"
: "${ACR_LOGIN_SERVER:?missing ACR_LOGIN_SERVER}"
: "${FOUNDRY_PROJECT_ENDPOINT:?missing FOUNDRY_PROJECT_ENDPOINT}"
: "${AZURE_AI_PROJECT_ID:?missing AZURE_AI_PROJECT_ID}"
: "${FOUNDRY_MODEL_DEPLOYMENT:?missing FOUNDRY_MODEL_DEPLOYMENT}"
: "${MCP_AUTH_APP_CLIENT_ID:?missing MCP_AUTH_APP_CLIENT_ID}"
: "${MCP_ACA_JOBS_COSMOS_ENDPOINT:?missing MCP_ACA_JOBS_COSMOS_ENDPOINT}"
: "${MCP_ACA_JOBS_STORAGE_ACCOUNT_URL:?missing MCP_ACA_JOBS_STORAGE_ACCOUNT_URL}"

ACR_NAME="${ACR_NAME:-${ACR_LOGIN_SERVER%%.*}}"
MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME="$(
  python3 -c 'import os,urllib.parse; print((urllib.parse.urlsplit(os.environ["MCP_ACA_JOBS_STORAGE_ACCOUNT_URL"]).hostname or "").split(".")[0])'
)"
MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME="$(
  python3 -c 'import os,urllib.parse; print((urllib.parse.urlsplit(os.environ["MCP_ACA_JOBS_COSMOS_ENDPOINT"]).hostname or "").split(".")[0])'
)"
MCP_ACA_JOBS_COSMOS_USE_EXISTING_ACCOUNT=true
export ACR_NAME MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME
export MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME MCP_ACA_JOBS_COSMOS_USE_EXISTING_ACCOUNT
echo "ACR_NAME=${ACR_NAME:+set}"
echo "MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME=${MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME:+set}"
echo "MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME=${MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME:+set}"
echo "MCP_ACA_JOBS_COSMOS_USE_EXISTING_ACCOUNT=${MCP_ACA_JOBS_COSMOS_USE_EXISTING_ACCOUNT:+set}"
az account show --output table || echo "(az cache not inherited — relying on azd auth login below)"
azd auth login \
  --federated-credential-provider github \
  --client-id "$AZURE_CLIENT_ID" \
  --tenant-id "$AZURE_TENANT_ID"
```

If any env var prints empty, the workflow’s `env:` block is broken. That is a workflow bug, not a skill bug.

---

## Step 1 — goal and constraints

You will deploy the canonical `foundry-mcp-aca-jobs` template into `$GITHUB_WORKSPACE/.scratch/` and prove the documented control plane and client contracts work.

Use these CI-safe names:

- resource group: `rg-awesome-gbb-ci`
- Container Apps environment: `cae-awesome-gbb-ci`
- every generated resource name must include a short UUID suffix

Create a state file under `.scratch/` and use it to persist the derived names between Bash calls. Use a UUID suffix like:

```bash
SUFFIX="$(uuidgen | tr 'A-Z' 'a-z' | cut -c1-8)"
```

Do not install tooling or hunt for binaries. `az`, `azd`, `curl`, `jq`, `python3`, and `uuidgen` are already available.

Required contract notes:

- use the existing storage account from env; do not provision a new one
- use unique Cosmos database/container names derived from the UUID suffix
- brownfield Cosmos CI mode must target the standing account and create only the UUID database/container
- keep all repo writes inside `.scratch/`
- do not grant ad hoc RBAC
- do not browse the repository
- do not use `/tmp`

---

## Step 2 — deterministic scaffold

Copy the canonical template files into a scratch workspace and write the exact `azd` environment file before any `azd up`. Do not hand-author source files.

```bash
set -Eeuo pipefail
SUFFIX="$(uuidgen | tr 'A-Z' 'a-z' | cut -c1-8)"
PROJECT_DIR="$GITHUB_WORKSPACE/.scratch/ci-smoke-mcp-jobs-$SUFFIX"
AZD_ENV_NAME="ci-smoke-mcp-jobs-$SUFFIX"
STATE_FILE="$GITHUB_WORKSPACE/.scratch/ci-smoke-mcp-jobs-state.env"
ACR_NAME="${ACR_LOGIN_SERVER%%.*}"
MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME="$(
  python3 -c 'import os,urllib.parse; print((urllib.parse.urlsplit(os.environ["MCP_ACA_JOBS_STORAGE_ACCOUNT_URL"]).hostname or "").split(".")[0])'
)"
MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME="$(
  python3 -c 'import os,urllib.parse; print((urllib.parse.urlsplit(os.environ["MCP_ACA_JOBS_COSMOS_ENDPOINT"]).hostname or "").split(".")[0])'
)"
MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME="mcpjobs-$SUFFIX"
export ACR_NAME MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME
export MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME
mkdir -p "$GITHUB_WORKSPACE/.scratch"
python3 skills/foundry-mcp-aca-jobs/test-fixture/run_e2e.py scaffold \
  --project-dir "$PROJECT_DIR" \
  --env-name "$AZD_ENV_NAME" \
  --resource-group "rg-awesome-gbb-ci" \
  --location "swedencentral" \
  --environment-name "cae-awesome-gbb-ci" \
  --app-name "ci-smoke-mcp-jobs-$SUFFIX" \
  --job-name "ci-smoke-mcp-jobs-worker-$SUFFIX" \
  --storage-account-url "$MCP_ACA_JOBS_STORAGE_ACCOUNT_URL" \
  --storage-account-name "$MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME" \
  --output-container-name "$MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME" \
  --cosmos-endpoint "$MCP_ACA_JOBS_COSMOS_ENDPOINT" \
  --cosmos-account-name "$MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME" \
  --cosmos-database-name "ci-smoke-mcp-jobs-db-$SUFFIX" \
  --cosmos-container-name "ci-smoke-mcp-jobs-task-$SUFFIX" \
  --cosmos-use-existing-account \
  --cosmos-existing-account-endpoint "$MCP_ACA_JOBS_COSMOS_ENDPOINT" \
  --service-mcp-image-name "$ACR_LOGIN_SERVER/mcp/service:ci-smoke-$SUFFIX" \
  --acr-name "$ACR_NAME" \
  --acr-login-server "$ACR_LOGIN_SERVER" \
  --azure-client-id "$AZURE_CLIENT_ID" \
  --azure-tenant-id "$AZURE_TENANT_ID" \
  --azure-subscription-id "$AZURE_SUBSCRIPTION_ID" \
  --mcp-auth-app-client-id "$MCP_AUTH_APP_CLIENT_ID" \
  --foundry-project-endpoint "$FOUNDRY_PROJECT_ENDPOINT" \
  --azure-ai-project-id "$AZURE_AI_PROJECT_ID" \
  --model-deployment "$FOUNDRY_MODEL_DEPLOYMENT"

{
  printf 'PROJECT_DIR=%s\n' "$PROJECT_DIR"
  printf 'STATE_FILE=%s\n' "$STATE_FILE"
  printf 'AZD_ENV_NAME=%s\n' "$AZD_ENV_NAME"
  printf 'SUFFIX=%s\n' "$SUFFIX"
  printf 'APP_NAME=%s\n' "ci-smoke-mcp-jobs-$SUFFIX"
  printf 'JOB_NAME=%s\n' "ci-smoke-mcp-jobs-worker-$SUFFIX"
  printf 'COSMOS_DATABASE_NAME=%s\n' "ci-smoke-mcp-jobs-db-$SUFFIX"
  printf 'COSMOS_CONTAINER_NAME=%s\n' "ci-smoke-mcp-jobs-task-$SUFFIX"
} > "$STATE_FILE"
```

No repository writes outside `.scratch/`.

---

## Step 3 — provider and build verification

1. Prove the Microsoft.App provider exposes the five custom role actions the skill documents.
2. Run `azd up` exactly once. It must build one image and converge the app and job onto the same digest.
3. Verify the deployed app and job both use that exact same digest and the expected commands.

Required success markers:

- `RBAC_PROVIDER_ACTIONS_MATCH`
- `SHARED_IMAGE_DIGEST_MATCH`
- `ENTRYPOINTS_MATCH`

Provider actions to prove, exactly:

- `Microsoft.App/jobs/read`
- `Microsoft.App/jobs/start/action`
- `Microsoft.App/jobs/execution/read`
- `Microsoft.App/jobs/executions/read`
- `Microsoft.App/jobs/stop/execution/action`

The hard gate is the deployed digest/command contract. Use the scratch state file, not ad hoc shell variables, to keep the names stable.

```bash
set -Eeuo pipefail
# shellcheck disable=SC1090
source "$GITHUB_WORKSPACE/.scratch/ci-smoke-mcp-jobs-state.env"
python3 skills/foundry-mcp-aca-jobs/test-fixture/run_e2e.py provider --project-dir "$PROJECT_DIR"
python3 skills/foundry-mcp-aca-jobs/test-fixture/run_e2e.py deploy \
  --project-dir "$PROJECT_DIR" \
  --env-name "$AZD_ENV_NAME"
source "$GITHUB_WORKSPACE/.scratch/ci-smoke-mcp-jobs-state.env"
```

The digest verification block must run the canonical helpers: `converge_image.py` and `verify_deployment.py`. It must check the exact app/job command arrays `['python', '-m', 'app.mcp_server']` and `['python', '-m', 'app.job_worker']`.

---

## Step 4 — task-aware and fallback client smoke

First prove the standards-first path:

- use `FastMCP Client`
- attach `TasksClientExtension()`
- pass the raw access token string as `auth=access_token`
- start a short job
- poll `tasks/get` until terminal

The direct path must write:

- `MCP_TASKS_COMPLETED`

Then prove the compatibility path without the Tasks extension:

- start the same job through the plain tool path
- poll status
- cancel immediately
- verify the fallback tools work

The fallback path must write:

- `FALLBACK_TOOLS_COMPLETED`

Duplicate submission with the same idempotency key must return the same task ID and same result:

- `IDEMPOTENCY_DUPLICATE_SAME_TASK`

The callback receiver must capture the exact four fields and only a credential-free result URL:

- `CALLBACK_PAYLOAD_VALID`

Cancellation must reach a terminal state:

- `CANCELLATION_TERMINAL`

```bash
set -Eeuo pipefail
# shellcheck disable=SC1090
source "$GITHUB_WORKSPACE/.scratch/ci-smoke-mcp-jobs-state.env"
python3 skills/foundry-mcp-aca-jobs/test-fixture/run_e2e.py tasks \
  --project-dir "$PROJECT_DIR" \
  --mcp-auth-app-client-id "$MCP_AUTH_APP_CLIENT_ID"
```

The direct path must use `FastMCP Client` + `TasksClientExtension`; the fallback path must use a normal `Client` with `mode="legacy"` and `extensions=[]` so FastMCP 4's automatic internal Tasks extension is inert. Assert `resultType` absence, immediate start/status/cancel, and the duplicate-task identity check.

---

## Step 5 — prompt agent smoke

Use the current `foundry-prompt-agents` APIs:

- `PromptAgentDefinition`
- `MCPTool`
- `create_version`
- `openai.conversations.create()`
- `openai.responses.create()`
- `delete_version()`

The prompt agent must call the fallback `start_aca_job` and `get_aca_job_status` tools against the deployed MCP endpoint and then write:

- `PROMPT_AGENT_MCP_PASS`

```bash
set -Eeuo pipefail
# shellcheck disable=SC1090
source "$GITHUB_WORKSPACE/.scratch/ci-smoke-mcp-jobs-state.env"
python3 skills/foundry-mcp-aca-jobs/test-fixture/run_e2e.py prompt-agent \
  --project-dir "$PROJECT_DIR" \
  --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT" \
  --mcp-auth-app-client-id "$MCP_AUTH_APP_CLIENT_ID"
```

The prompt agent must create a unique version, create a conversation, invoke the agent through `openai.responses.create(...)`, and best-effort delete the version afterward.

---

## Step 6 — hosted agent smoke

Use the current hosted-agent APIs:

- `FoundryChatClient.get_mcp_tool(...)`
- `Agent`
- `ResponsesHostServer`

The hosted agent must deploy a unique hosted-agent version, invoke it against the same fallback `start_aca_job` and `get_aca_job_status` tools, and then write:

- `HOSTED_AGENT_MCP_PASS`

```bash
set -Eeuo pipefail
# shellcheck disable=SC1090
source "$GITHUB_WORKSPACE/.scratch/ci-smoke-mcp-jobs-state.env"
python3 skills/foundry-mcp-aca-jobs/test-fixture/run_e2e.py hosted-agent \
  --project-dir "$PROJECT_DIR" \
  --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT" \
  --mcp-auth-app-client-id "$MCP_AUTH_APP_CLIENT_ID"
```

The hosted agent must use `FoundryChatClient.get_mcp_tool(name=..., url=..., headers={"Authorization": ...}, approval_mode="never_require")`, invoke the agent through the Foundry project endpoint, and best-effort delete its version afterward.

---

## Step 7 — marker-first teardown

Once all hard gates pass, write the exact PASS marker first:

```bash
set -Eeuo pipefail
# shellcheck disable=SC1090
source "$GITHUB_WORKSPACE/.scratch/ci-smoke-mcp-jobs-state.env"
printf 'SMOKE_RESULT=PASS\n' > "$PROJECT_DIR/.foundry-mcp-aca-jobs-smoke-result"
```

Then do a five-minute best-effort targeted cleanup of the scratch workspace and the Azure resources you created. If teardown fails or times out, keep the PASS marker and stop. Cleanup is hygiene, not the contract.

```bash
set -Eeuo pipefail
# shellcheck disable=SC1090
source "$GITHUB_WORKSPACE/.scratch/ci-smoke-mcp-jobs-state.env"
python3 skills/foundry-mcp-aca-jobs/test-fixture/run_e2e.py cleanup --project-dir "$PROJECT_DIR"
```

The final cleanup phase should only touch what this smoke created.

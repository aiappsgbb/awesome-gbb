# Customer goal — `foundry-mcp-aca-jobs` skill smoke

You are a developer on a customer team. You installed the `awesome-gbb`
Copilot CLI plugin and want to prove that the `foundry-mcp-aca-jobs` skill
works end-to-end against the CI Foundry project.

Do whatever the skill tells you to do. Read the skill’s `SKILL.md` first, but
do not browse the repository or improvise from training-data memory. This is an
execution smoke, not a catalog inspection.

**CRITICAL — execution smoke, no repo browsing.** Do NOT browse the repository.
Do NOT view files, glob, grep, or search for fixes. The first Bash action must be
`echo "skills/foundry-mcp-aca-jobs/SKILL.md"`.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You are the
running Copilot CLI process. Do not run `copilot -p`, `copilot --version`,
`npm install -g @github/copilot`, or any other `copilot ...` invocation from
inside Bash. The workflow already captures your output; your job is to execute
the smoke steps directly.

---

## Step -1 — acknowledge the skill contract

Your first Bash action must be:

```bash
echo "skills/foundry-mcp-aca-jobs/SKILL.md"
```

Do not open any other repository file.

---

## Step 0 — auth context (show, do not assert)

Print the auth context for the run log. Hard-fail if any required value is
missing. Do not compare subscription IDs, decode tokens, or gate on Azure CLI
cache visibility.

```bash
set -Eeuo pipefail
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "ACR_LOGIN_SERVER=${ACR_LOGIN_SERVER:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
echo "AZURE_AI_PROJECT_ID=${AZURE_AI_PROJECT_ID:+set}"
echo "MCP_AUTH_APP_CLIENT_ID=${MCP_AUTH_APP_CLIENT_ID:+set}"
echo "MCP_ACA_JOBS_COSMOS_ENDPOINT=${MCP_ACA_JOBS_COSMOS_ENDPOINT:+set}"
echo "MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME=${MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME:+set}"
echo "MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME=${MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME:+set}"
test -n "${AZURE_CLIENT_ID:-}" || { printf 'SMOKE_RESULT=FAIL missing AZURE_CLIENT_ID\n' > /tmp/foundry-mcp-aca-jobs-smoke-result; exit 1; }
test -n "${AZURE_TENANT_ID:-}" || { printf 'SMOKE_RESULT=FAIL missing AZURE_TENANT_ID\n' > /tmp/foundry-mcp-aca-jobs-smoke-result; exit 1; }
test -n "${AZURE_SUBSCRIPTION_ID:-}" || { printf 'SMOKE_RESULT=FAIL missing AZURE_SUBSCRIPTION_ID\n' > /tmp/foundry-mcp-aca-jobs-smoke-result; exit 1; }
test -n "${ACR_LOGIN_SERVER:-}" || { printf 'SMOKE_RESULT=FAIL missing ACR_LOGIN_SERVER\n' > /tmp/foundry-mcp-aca-jobs-smoke-result; exit 1; }
test -n "${FOUNDRY_PROJECT_ENDPOINT:-}" || { printf 'SMOKE_RESULT=FAIL missing FOUNDRY_PROJECT_ENDPOINT\n' > /tmp/foundry-mcp-aca-jobs-smoke-result; exit 1; }
test -n "${AZURE_AI_PROJECT_ID:-}" || { printf 'SMOKE_RESULT=FAIL missing AZURE_AI_PROJECT_ID\n' > /tmp/foundry-mcp-aca-jobs-smoke-result; exit 1; }
test -n "${MCP_AUTH_APP_CLIENT_ID:-}" || { printf 'SMOKE_RESULT=FAIL missing MCP_AUTH_APP_CLIENT_ID\n' > /tmp/foundry-mcp-aca-jobs-smoke-result; exit 1; }
test -n "${MCP_ACA_JOBS_COSMOS_ENDPOINT:-}" || { printf 'SMOKE_RESULT=FAIL missing MCP_ACA_JOBS_COSMOS_ENDPOINT\n' > /tmp/foundry-mcp-aca-jobs-smoke-result; exit 1; }
test -n "${MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME:-}" || { printf 'SMOKE_RESULT=FAIL missing MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME\n' > /tmp/foundry-mcp-aca-jobs-smoke-result; exit 1; }
test -n "${MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME:-}" || { printf 'SMOKE_RESULT=FAIL missing MCP_ACA_JOBS_OUTPUT_CONTAINER_NAME\n' > /tmp/foundry-mcp-aca-jobs-smoke-result; exit 1; }
az account show --output table || echo "(az cache not inherited — relying on azd auth login below)"
azd auth login \
  --federated-credential-provider github \
  --client-id "$AZURE_CLIENT_ID" \
  --tenant-id "$AZURE_TENANT_ID"
```

If any env var prints empty, the workflow’s `env:` block is broken. That is a
workflow bug, not a skill bug.

---

## Step 1 — goal and constraints

You will deploy the canonical `foundry-mcp-aca-jobs` template into
`$GITHUB_WORKSPACE/.scratch/` and prove the documented control plane and client
contracts work.

Use these CI-safe names:

- resource group: `rg-awesome-gbb-ci`
- Container Apps environment: `cae-awesome-gbb-ci`
- every generated resource name must include a short UUID suffix

Create a state file under `.scratch/` and use it to persist the derived names
between Bash calls. Use a UUID suffix like:

```bash
SUFFIX="$(uuidgen | tr 'A-Z' 'a-z' | cut -c1-8)"
```

Do not install tooling or hunt for binaries. `az`, `azd`, `docker`, `curl`,
`jq`, `python3`, and `uuidgen` are already available.

Required contract notes:

- use the existing storage account from env; do not provision a new one
- use unique Cosmos database/container names derived from the UUID suffix
- keep all repo writes inside `.scratch/`
- do not grant ad hoc RBAC
- do not browse the repository

---

## Step 2 — deterministic scaffold

Copy the canonical template files into a scratch workspace. Do not hand-author
source files.

```bash
set -Eeuo pipefail
SUFFIX="$(uuidgen | tr 'A-Z' 'a-z' | cut -c1-8)"
PROJECT_DIR="$GITHUB_WORKSPACE/.scratch/ci-smoke-mcp-jobs-$SUFFIX"
STATE_FILE="$PROJECT_DIR/state.env"
STATE_TMP="$STATE_FILE.tmp"
mkdir -p \
  "$PROJECT_DIR/infra/identity-rbac" \
  "$PROJECT_DIR/infra/scripts" \
  "$GITHUB_WORKSPACE/.scratch/azd-patterns/references/bicep"

cp skills/foundry-mcp-aca-jobs/templates/azure.yaml "$PROJECT_DIR/azure.yaml"
cp skills/foundry-mcp-aca-jobs/templates/Dockerfile "$PROJECT_DIR/Dockerfile"
cp skills/foundry-mcp-aca-jobs/templates/pyproject.toml "$PROJECT_DIR/pyproject.toml"
cp skills/foundry-mcp-aca-jobs/templates/infra/main.bicep "$PROJECT_DIR/infra/main.bicep"
cp skills/foundry-mcp-aca-jobs/templates/infra/app.bicep "$PROJECT_DIR/infra/app.bicep"
cp skills/foundry-mcp-aca-jobs/templates/infra/cosmos.bicep "$PROJECT_DIR/infra/cosmos.bicep"
cp skills/foundry-mcp-aca-jobs/templates/infra/identity-rbac.bicep "$PROJECT_DIR/infra/identity-rbac.bicep"
cp skills/foundry-mcp-aca-jobs/templates/infra/identity-rbac/assignments.bicep "$PROJECT_DIR/infra/identity-rbac/assignments.bicep"
cp skills/foundry-mcp-aca-jobs/templates/infra/identity-rbac/job-operator.bicep "$PROJECT_DIR/infra/identity-rbac/job-operator.bicep"
cp skills/foundry-mcp-aca-jobs/templates/infra/identity-rbac/uami.bicep "$PROJECT_DIR/infra/identity-rbac/uami.bicep"
cp skills/foundry-mcp-aca-jobs/templates/infra/scripts/converge_image.py "$PROJECT_DIR/infra/scripts/converge_image.py"
cp skills/foundry-mcp-aca-jobs/templates/infra/scripts/verify_deployment.py "$PROJECT_DIR/infra/scripts/verify_deployment.py"
cp skills/foundry-mcp-aca-jobs/templates/infra/scripts/pyproject.toml "$PROJECT_DIR/infra/scripts/pyproject.toml"
cp skills/foundry-mcp-aca-jobs/templates/infra/scripts/uv.lock "$PROJECT_DIR/infra/scripts/uv.lock"
cp skills/azd-patterns/references/bicep/aca-job.bicep "$GITHUB_WORKSPACE/.scratch/azd-patterns/references/bicep/aca-job.bicep"

{
  printf 'PROJECT_DIR=%s\n' "$PROJECT_DIR"
  printf 'STATE_FILE=%s\n' "$STATE_FILE"
  printf 'SUFFIX=%s\n' "$SUFFIX"
  printf 'APP_NAME=%s\n' "ci-smoke-mcp-jobs-$SUFFIX"
  printf 'JOB_NAME=%s\n' "ci-smoke-mcp-jobs-worker-$SUFFIX"
  printf 'COSMOS_DATABASE_NAME=%s\n' "ci-smoke-mcp-jobs-db-$SUFFIX"
  printf 'COSMOS_CONTAINER_NAME=%s\n' "ci-smoke-mcp-jobs-task-$SUFFIX"
} > "$STATE_TMP"
mv "$STATE_TMP" "$STATE_FILE"
```

No repository writes outside `.scratch/`.

---

## Step 3 — provider and build verification

1. Prove the Microsoft.App provider exposes the five custom role actions the
   skill documents.
2. Run `azd up` exactly once. It must build one image and converge the app and
   job onto the same digest.
3. Verify the deployed app and job both use that exact same digest and the
   expected commands.

Required success markers:

- `RBAC_PROVIDER_ACTIONS_MATCH`
- `SHARED_IMAGE_DIGEST_MATCH`
- `ENTRYPOINTS_MATCH`

The provider probe must use:

```bash
az provider operation show --namespace Microsoft.App
```

The hard gate is the deployed digest/command contract. Use the scratch state
file, not ad hoc shell variables, to keep the names stable.

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

Duplicate submission with the same idempotency key must return the same task ID
and same result:

- `IDEMPOTENCY_DUPLICATE_SAME_TASK`

The callback receiver must capture the exact four fields and only a
credential-free result URL:

- `CALLBACK_PAYLOAD_VALID`

Cancellation must reach a terminal state:

- `CANCELLATION_TERMINAL`

---

## Step 5 — prompt agent smoke

Use the current `foundry-prompt-agents` APIs:

- `PromptAgentDefinition`
- `MCPTool`

The prompt agent must call the fallback `start_aca_job` and
`get_aca_job_status` tools against the deployed MCP endpoint and then write:

- `PROMPT_AGENT_MCP_PASS`

Do not deploy a second hosted container for this check.

---

## Step 6 — hosted agent smoke

Use the current hosted-agent APIs:

- `FoundryChatClient.get_mcp_tool(...)`
- `Agent`

The hosted agent must call the same fallback `start_aca_job` and
`get_aca_job_status` tools against the deployed MCP endpoint and then write:

- `HOSTED_AGENT_MCP_PASS`

---

## Step 7 — marker-first teardown

Once all hard gates pass, write the exact PASS marker first:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-mcp-aca-jobs-smoke-result
```

Then do a five-minute best-effort targeted cleanup of the scratch workspace and
the Azure resources you created. If teardown fails or times out, keep the PASS
marker and stop. Cleanup is hygiene, not the contract.

The final cleanup phase should only touch what this smoke created.

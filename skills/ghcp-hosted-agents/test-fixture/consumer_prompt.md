# Customer goal — `ghcp-hosted-agents` GA smoke

Execute a live GHCP SDK hosted-agent GA smoke against the CI Foundry
project. This is an execution test, not a catalog-inspection task. Follow
the exact contract below; do not browse the repository or load the full
SKILL.md into context.

## Step -1 - acknowledge the skill contract

Your first Bash action must be:

```bash
echo "skills/ghcp-hosted-agents/SKILL.md"
```

This lightweight line is the workflow's skill-usage audit evidence. Do not
open the whole file.

**CRITICAL - never invoke `copilot` recursively from a Bash tool.** You are
the running Copilot CLI process. Do not run `copilot -p`, `copilot --version`,
install Copilot, or invoke any other `copilot` command. The workflow already
captures output through its outer `tee`; execute the smoke steps directly.

## Step 0 - auth context

The workflow has already installed `azd` at `/usr/local/bin/azd`. Do not search
the filesystem, run `command -v azd`, or install a replacement. Run:

```bash
rm -f \
  /tmp/ghcp-hosted-agents-smoke-result \
  /tmp/ghcp-hosted-agents-smoke-evidence \
  /tmp/ghcp-hosted-agents-agent-name \
  /tmp/ghcp-hosted-agents-invoke.log
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
echo "AZURE_AI_PROJECT_ID=${AZURE_AI_PROJECT_ID:+set}"
echo "ACR_LOGIN_SERVER=${ACR_LOGIN_SERVER:+set}"
test -n "${AZURE_CLIENT_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL missing AZURE_CLIENT_ID\n' > /tmp/ghcp-hosted-agents-smoke-result
  exit 1
}
test -n "${AZURE_TENANT_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL missing AZURE_TENANT_ID\n' > /tmp/ghcp-hosted-agents-smoke-result
  exit 1
}
test -n "${AZURE_SUBSCRIPTION_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL missing AZURE_SUBSCRIPTION_ID\n' > /tmp/ghcp-hosted-agents-smoke-result
  exit 1
}
test -n "${FOUNDRY_PROJECT_ENDPOINT:-}" || {
  printf 'SMOKE_RESULT=FAIL missing FOUNDRY_PROJECT_ENDPOINT\n' > /tmp/ghcp-hosted-agents-smoke-result
  exit 1
}
test -n "${AZURE_AI_PROJECT_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL missing AZURE_AI_PROJECT_ID\n' > /tmp/ghcp-hosted-agents-smoke-result
  exit 1
}
test -n "${ACR_LOGIN_SERVER:-}" || {
  printf 'SMOKE_RESULT=FAIL missing ACR_LOGIN_SERVER\n' > /tmp/ghcp-hosted-agents-smoke-result
  exit 1
}
if [[ "$ACR_LOGIN_SERVER" == *"://"* \
   || "$ACR_LOGIN_SERVER" == */* \
   || "$ACR_LOGIN_SERVER" != *.azurecr.io ]]; then
  printf 'SMOKE_RESULT=FAIL malformed ACR_LOGIN_SERVER\n' > /tmp/ghcp-hosted-agents-smoke-result
  exit 1
fi
az account show --output table || echo "(az cache not inherited - relying on azd auth login below)"
azd auth login \
  --federated-credential-provider github \
  --client-id "$AZURE_CLIENT_ID" \
  --tenant-id "$AZURE_TENANT_ID"
```

Assert that all six auth/deploy variables above are non-empty. Do not compare
subscription IDs, decode tokens, or gate on Azure CLI cache visibility.
`ACR_LOGIN_SERVER` must be a bare `<registry>.azurecr.io` hostname — no
scheme, path, or trailing slash. If a required environment variable is empty
or the registry host is malformed, write the matching FAIL marker and stop.
`azd auth login` is the explicit azd authentication gate; if it fails, use
the matching final-step marker.

**Pre-provisioned, do NOT create:** the Foundry project at
`FOUNDRY_PROJECT_ENDPOINT` and the container registry at `ACR_LOGIN_SERVER`
already exist. Direct-copy container deploy requires that registry hostname
for build/push, while deletion remains best-effort during teardown. Do not
run any `azd` provisioning command, `az group create`, or anything that
provisions a new Foundry project or registry. Hosted agents run on
Foundry-managed, per-session sandboxes - there is no Container Apps
environment, no ACA app, and nothing else to provision for this fixture.

**No agent role grant.** Per the skill's GA identity guidance, the hosted
agent's own Entra identity has implicit access to model inferencing and
session storage by default. Do NOT run any command that creates an Azure
RBAC role assignment against the agent's identity, and do NOT expect one to
be necessary. Any permission error is a hard FAIL except the exact immediate-post-active readiness envelope described in Step 4; that one
narrow case retries the same invoke path. Never route around a failure with
an ad hoc role grant.

## Step 1 - install and verify the azd Foundry extensions

```bash
azd ext install microsoft.foundry
extensions_json="$(azd ext list --output json)"
microsoft_foundry_version="$(jq -er \
  '[.[] | select(.id == "microsoft.foundry") | .installedVersion | select(type == "string" and length > 0)]
   | if length == 1 then .[0] else error("expected one installed microsoft.foundry extension") end' \
  <<<"$extensions_json")"
agents_extension_version="$(jq -er \
  '[.[] | select(.id == "azure.ai.agents") | .installedVersion | select(type == "string" and length > 0)]
   | if length == 1 then .[0] else error("expected one installed azure.ai.agents extension") end' \
  <<<"$extensions_json")"
printf 'AZD_EXTENSION_VERSION id=microsoft.foundry installedVersion=%s\n' \
  "$microsoft_foundry_version" >> /tmp/ghcp-hosted-agents-smoke-evidence
printf 'AZD_EXTENSION_VERSION id=microsoft.foundry installedVersion=%s\n' \
  "$microsoft_foundry_version"
printf 'AZD_EXTENSION_VERSION id=azure.ai.agents installedVersion=%s\n' \
  "$agents_extension_version" >> /tmp/ghcp-hosted-agents-smoke-evidence
printf 'AZD_EXTENSION_VERSION id=azure.ai.agents installedVersion=%s\n' \
  "$agents_extension_version"
```

The commands require exactly one installed version for both
`microsoft.foundry` and `azure.ai.agents`, then persist the non-sensitive
version values to smoke evidence. Do NOT rely on `azd ai agent version` or
any other version-probing command — `azd ext list --output json` is the only
supported way to verify this in the fixture.

## Step 2 - deploy the canonical container agent

Use a Bash heredoc to write the following script to
`/tmp/ghcp-hosted-agents-ga-smoke.sh`, then run it once:

```bash
#!/usr/bin/env bash
set -euo pipefail

evidence="/tmp/ghcp-hosted-agents-smoke-evidence"

record() {
  printf '%s\n' "$1" >>"$evidence"
  printf '%s\n' "$1"
}

suffix="$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')"
agent_name="ci-smoke-ghcp-${suffix}"
work_dir="/tmp/ghcp-hosted-agents-${suffix}"
mkdir -p "$work_dir"

# Copy the canonical reference files verbatim - do NOT hand-author these
# from training-data memory. SKILL.md's references/ directory is the
# single source of truth.
repo_root="${GITHUB_WORKSPACE:-$PWD}"
skill_refs="$repo_root/skills/ghcp-hosted-agents/references"
cp "$skill_refs/Dockerfile" "$work_dir/Dockerfile"
cp "$skill_refs/container.py" "$work_dir/container.py"
cp "$skill_refs/pyproject.toml" "$work_dir/pyproject.toml"
cp "$skill_refs/yaml/azure.yaml" "$work_dir/azure.yaml"

# Preserve the canonical YAML byte-for-byte except for the two exact
# UUID-bearing agent identifiers. Count each source token before replacing so
# an upstream reference change fails loudly instead of altering prose/comments.
AGENT_NAME="$agent_name" AZURE_YAML_PATH="$work_dir/azure.yaml" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["AZURE_YAML_PATH"])
agent_name = os.environ["AGENT_NAME"]
text = path.read_text(encoding="utf-8")
replacements = (
    ("  my-agent:\n", f"  {agent_name}:\n"),
    ("    name: my-agent\n", f"    name: {agent_name}\n"),
)
for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one canonical token {old!r}, found {count}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
PY

# Show and prove the exact canonical shape before deployment.
sed -n '1,160p' "$work_dir/azure.yaml"
AGENT_NAME="$agent_name" CANONICAL_YAML="$skill_refs/yaml/azure.yaml" \
  RENDERED_YAML="$work_dir/azure.yaml" python3 - <<'PY'
import os
from pathlib import Path

agent_name = os.environ["AGENT_NAME"]
canonical = Path(os.environ["CANONICAL_YAML"]).read_text(encoding="utf-8")
rendered = Path(os.environ["RENDERED_YAML"]).read_text(encoding="utf-8")
restored = rendered.replace(f"  {agent_name}:\n", "  my-agent:\n", 1)
restored = restored.replace(f"    name: {agent_name}\n", "    name: my-agent\n", 1)
assert restored == canonical, "rendered azure.yaml differs beyond agent identifiers"
assert "protocol: invocations" in rendered
assert "version: 2.0.0" in rendered
assert "environmentVariables:" in rendered
assert "provider: microsoft.foundry" in rendered
assert "endpoint: ${FOUNDRY_PROJECT_ENDPOINT}" in rendered
print(f"CANONICAL_AZURE_YAML_OK service={agent_name}")
PY

(
  cd "$work_dir"
  azd env new "$agent_name" --no-prompt
  azd env set AZURE_SUBSCRIPTION_ID "$AZURE_SUBSCRIPTION_ID"
  azd env set FOUNDRY_PROJECT_ENDPOINT "$FOUNDRY_PROJECT_ENDPOINT"
  azd env set AZURE_AI_PROJECT_ID "$AZURE_AI_PROJECT_ID"
  azd env set AZURE_CONTAINER_REGISTRY_ENDPOINT "$ACR_LOGIN_SERVER"
  azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "gpt-5.4-mini"

  verify_azd_value() {
    local key="$1"
    local value
    if ! value="$(azd env get-value "$key" 2>/dev/null)" || [[ -z "$value" ]]; then
      printf 'SMOKE_RESULT=FAIL azd env contract missing %s\n' "$key" \
        > /tmp/ghcp-hosted-agents-smoke-result
      exit 1
    fi
  }
  verify_azd_value AZURE_SUBSCRIPTION_ID
  verify_azd_value FOUNDRY_PROJECT_ENDPOINT
  verify_azd_value AZURE_AI_PROJECT_ID
  verify_azd_value AZURE_CONTAINER_REGISTRY_ENDPOINT
  verify_azd_value AZURE_AI_MODEL_DEPLOYMENT_NAME
  record "AZD_ENV_CONTRACT_OK"
  record "AZD_DEPLOY_ATTEMPT count=1"
  azd deploy "$agent_name" --no-prompt
)
record "AZD_DEPLOY_SUCCEEDED name=${agent_name}"
echo "$agent_name" > /tmp/ghcp-hosted-agents-agent-name
echo "$work_dir" > /tmp/ghcp-hosted-agents-work-dir
```

```bash
bash /tmp/ghcp-hosted-agents-ga-smoke.sh
```

If `azd deploy` fails with a permission/authorization error, that is a hard
FAIL (see the "No agent role grant" note above) - do not attempt to work
around it with a manual role assignment. **The deploy command above is the
only deploy attempt.** On any failure, do not rerun deploy, query Azure to
discover replacement values, hardcode inventory, or modify the azd env.
Write the matching FAIL marker and stop.

## Step 3 - GA SDK hard check: agent version active (deterministic, no preview surfaces)

Create an isolated virtual environment and install the bounded stable stack:

```bash
python3 -m venv /tmp/ghcp-hosted-agents-venv
/tmp/ghcp-hosted-agents-venv/bin/pip install --quiet \
  "azure-ai-projects~=2.3.0" \
  "azure-identity~=1.25.3"
```

Use a Bash heredoc to write the following program to
`/tmp/ghcp-hosted-agents-version-check.py`, then run it once with
`/tmp/ghcp-hosted-agents-venv/bin/python`:

```python
import os
import time

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

evidence_path = "/tmp/ghcp-hosted-agents-smoke-evidence"


def record(message: str) -> None:
    print(message)
    with open(evidence_path, "a", encoding="utf-8") as evidence:
        evidence.write(f"{message}\n")


with open("/tmp/ghcp-hosted-agents-agent-name", encoding="utf-8") as f:
    agent_name = f.read().strip()

endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]

with DefaultAzureCredential() as credential, AIProjectClient(
    endpoint=endpoint, credential=credential
) as project:
    # Bounded readiness retry - GA provisioning is typically < 1 minute,
    # but cold starts vary. Do NOT poll forever.
    version = None
    for attempt in range(18):
        version = project.agents.get_version(agent_name=agent_name, agent_version="1")
        if version["status"] == "active":
            break
        if version["status"] == "failed":
            raise RuntimeError(f"agent version failed to provision: {dict(version)}")
        time.sleep(10)
    assert version is not None and version["status"] == "active", (
        f"agent version never reached active: {dict(version) if version else None}"
    )
    protocol_versions = version["definition"]["protocol_versions"]
    assert any(
        p["protocol"] == "invocations" and p["version"] == "2.0.0"
        for p in protocol_versions
    ), f"expected invocations protocol 2.0.0, got {protocol_versions}"
    record(f"AGENT_VERSION_ACTIVE name={agent_name} protocol=invocations/2.0.0")
```

Do not use `allow_preview=True`, `project.beta.agents.patch_agent_details`,
protocol version `"1.0.0"`/`"v1"`, or a `Foundry-Features` preview header. A
permission error during deploy or the version check is a hard FAIL. The only
retryable permission case is the exact immediate-post-active readiness
envelope classified in Step 4. Do not attempt a manual role assignment to
work around either case.

## Step 4 - invoke via `azd ai agent invoke` (single documented path)

Per SKILL.md § "Invoking the Agent", `azd ai agent invoke` is the primary
documented path on GA. Use only this path, with a bounded retry for the exact
post-deploy implicit-permission readiness envelope observed in live CI. Capture
stdout without a fixture-local `tee` (the workflow already captures the full
transcript):

```bash
work_dir="$(cat /tmp/ghcp-hosted-agents-work-dir)"
agent_name="$(cat /tmp/ghcp-hosted-agents-agent-name)"
invoke_log="/tmp/ghcp-hosted-agents-invoke.log"
cd "$work_dir"
invoke_ok=0
for attempt in 1 2 3 4 5 6; do
  rm -f "$invoke_log"
  set +e
  timeout 300 azd ai agent invoke "$agent_name" \
    '{"input":"Say hello in one short sentence."}' \
    --protocol invocations \
    --output raw \
    --timeout 180 >"$invoke_log" 2>&1
  invoke_status=$?
  set -e
  cat "$invoke_log"
  printf 'INVOKE_ATTEMPT count=%s exitStatus=%s\n' "$attempt" "$invoke_status" \
    >> /tmp/ghcp-hosted-agents-smoke-evidence

  if (( invoke_status != 0 )); then
    printf 'SMOKE_RESULT=FAIL invoke command exited with status %s\n' "$invoke_status" \
      > /tmp/ghcp-hosted-agents-smoke-result
    exit 1
  fi

  set +e
  python3 - "$invoke_log" <<'PY'
import json
import sys
from pathlib import Path

success = False
# 0=none, 1=anchored failures, 2=generic failures, 3=session retry, 4=terminal 401
readiness_state = 0
unrelated_terminal_error = False
malformed_data = False
for line in Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines():
    if not line.startswith("data:"):
        continue
    payload = line[5:].lstrip()
    if not payload:
        malformed_data = True
        continue
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        malformed_data = True
        continue
    if not isinstance(event, dict):
        malformed_data = True
        continue
    event_type = event.get("type")
    if event_type in {"assistant.message", "assistant.message_delta"}:
        success = True
    elif event_type == "model.call_failure":
        data = event.get("data") or {}
        if not isinstance(data, dict):
            malformed_data = True
            continue
        error_message = str(data.get("errorMessage", ""))
        if data.get("statusCode") == 401 and "PermissionDenied" in error_message:
            # The first event in the exact live readiness envelope names the
            # missing project-scoped Responses action and request path.
            anchored = (
                "Microsoft.CognitiveServices/accounts/OpenAI/responses/write"
                in error_message
                and "POST /openai/v1/responses" in error_message
            )
            if anchored and not success and readiness_state in {0, 1}:
                readiness_state = 1
            # Subsequent generic 401 PermissionDenied model failures are part
            # of the same envelope, but cannot establish readiness alone.
            elif not anchored and not success and readiness_state in {1, 2}:
                readiness_state = 2
            else:
                unrelated_terminal_error = True
        else:
            unrelated_terminal_error = True
    elif event_type == "session.info":
        data = event.get("data")
        if not isinstance(data, dict):
            malformed_data = True
            continue
        if "transient_auth_error" in str(data.get("message", "")):
            if not success and readiness_state in {1, 2, 3}:
                readiness_state = 3
            else:
                unrelated_terminal_error = True
    elif event_type == "error":
        message = str(event.get("message", ""))
        if (
            "Authentication failed with provider" in message
            and "HTTP 401" in message
            and not success
            and readiness_state == 3
        ):
            readiness_state = 4
        else:
            unrelated_terminal_error = True

if malformed_data or unrelated_terminal_error:
    raise SystemExit(20)
if success:
    raise SystemExit(0 if readiness_state in {0, 4} else 20)
if readiness_state == 4:
    raise SystemExit(10)
raise SystemExit(20)
PY
  envelope_status=$?
  set -e

  if (( envelope_status == 0 )); then
    printf 'INVOKE_OK name=%s attempt=%s\n' "$agent_name" "$attempt" \
      >> /tmp/ghcp-hosted-agents-smoke-evidence
    printf 'INVOKE_OK name=%s attempt=%s\n' "$agent_name" "$attempt"
    invoke_ok=1
    break
  fi
  if (( envelope_status == 10 )); then
    printf 'INVOKE_TRANSIENT_AUTH attempt=%s\n' "$attempt" \
      >> /tmp/ghcp-hosted-agents-smoke-evidence
    if (( attempt < 6 )); then
      sleep 15
      continue
    fi
    printf 'SMOKE_RESULT=FAIL implicit permission not ready after 6 invoke attempts\n' \
      > /tmp/ghcp-hosted-agents-smoke-result
    exit 1
  fi

  printf 'SMOKE_RESULT=FAIL invoke returned terminal SSE error without assistant event\n' \
    > /tmp/ghcp-hosted-agents-smoke-result
  exit 1
done

if (( invoke_ok != 1 )); then
  printf 'SMOKE_RESULT=FAIL invoke did not return assistant.message or assistant.message_delta\n' \
    > /tmp/ghcp-hosted-agents-smoke-result
  exit 1
fi
```

Do not use `curl`, a hand-rolled REST call, or `references/invoke_agent.py`
here - `azd ai agent invoke` is the single documented path for this fixture
(Pattern 16, AGENTS.md § 9.7). Retry only the confirmed HTTP-200 SSE
readiness envelope (`model.call_failure`, status 401, `PermissionDenied` /
`transient_auth_error`) with six attempts and 15-second backoff. A nonzero
CLI exit or any other terminal envelope is a hard FAIL. Do not add a role
grant. The last exact raw response is persisted to
`/tmp/ghcp-hosted-agents-invoke.log`; the workflow snapshots it under an
attempt-specific filename before any retry and uploads both attempts.

## Step 5 - best-effort teardown

Read the agent name persisted in Step 2 and perform teardown in a bounded
300-second window. A failure or timeout here does NOT affect the PASS marker -
print one NOTE to stdout and continue to Step 6. The CI resource group is
periodically pruned of orphaned hosted-agent versions and ACR repositories
by a separate janitor.

```bash
agent_name="$(cat /tmp/ghcp-hosted-agents-agent-name)"
timeout 300 azd ai agent delete "$agent_name" --force --no-prompt \
  && printf 'AGENT_DELETED name=%s\n' "$agent_name" >> /tmp/ghcp-hosted-agents-smoke-evidence \
  || echo "NOTE best-effort teardown exceeded 300-second cap or encountered an error; CI janitor will prune orphaned resources"
```

Do NOT run a full-environment teardown command, a container-app cleanup
command, or a registry-repository delete command - hosted agents run on
Foundry-managed sandboxes, and there is no Container Apps environment or
ACR repository owned by this fixture to clean up beyond the agent record
itself.

## Step 6 - Marker contract

After the invoke check passes, verify the evidence file contains every
required success record below (teardown records are best-effort and not
checked here):

```bash
python3 - <<'PY'
from pathlib import Path
import re

lines = Path("/tmp/ghcp-hosted-agents-smoke-evidence").read_text(
    encoding="utf-8"
).splitlines()
required_patterns = (
    r"AZD_EXTENSION_VERSION id=microsoft\.foundry installedVersion=\S+",
    r"AZD_EXTENSION_VERSION id=azure\.ai\.agents installedVersion=\S+",
    r"AZD_ENV_CONTRACT_OK",
    r"AZD_DEPLOY_ATTEMPT count=1",
    r"AZD_DEPLOY_SUCCEEDED name=ci-smoke-ghcp-[0-9a-f]{8}",
    r"AGENT_VERSION_ACTIVE name=ci-smoke-ghcp-[0-9a-f]{8} protocol=invocations/2\.0\.0",
    r"INVOKE_OK name=ci-smoke-ghcp-[0-9a-f]{8} attempt=[1-6]",
)
for pattern in required_patterns:
    assert any(re.fullmatch(pattern, line) for line in lines), (pattern, lines)
attempts = [line for line in lines if line.startswith("AZD_DEPLOY_ATTEMPT ")]
assert attempts == ["AZD_DEPLOY_ATTEMPT count=1"], attempts
invoke_attempts = [line for line in lines if line.startswith("INVOKE_ATTEMPT ")]
assert 1 <= len(invoke_attempts) <= 6, invoke_attempts
for expected, line in enumerate(invoke_attempts, start=1):
    assert line.startswith(f"INVOKE_ATTEMPT count={expected} "), invoke_attempts
PY
```

Only after that check succeeds, your final Bash action is:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/ghcp-hosted-agents-smoke-result
```

If teardown (Step 5) left a `NOTE` line in the evidence
file, that does NOT block PASS - teardown is best-effort (300-second cap).
The CI resource group is periodically pruned of orphaned hosted-agent
versions and ACR repositories by a separate janitor.

If a required step fails, choose exactly one matching command below as your
final Bash action:

```bash
printf 'SMOKE_RESULT=FAIL missing AZURE_CLIENT_ID\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL missing AZURE_TENANT_ID\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL missing AZURE_SUBSCRIPTION_ID\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL missing FOUNDRY_PROJECT_ENDPOINT\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL missing AZURE_AI_PROJECT_ID\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL missing ACR_LOGIN_SERVER\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL malformed ACR_LOGIN_SERVER\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL azd auth login failed\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL microsoft.foundry or azure.ai.agents extension not installed\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL azd env contract incomplete\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL azd deploy failed\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL permission denied - agent identity should have implicit access by default\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL agent version never reached active\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL protocol version mismatch - expected invocations 2.0.0\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL invoke command exited non-zero\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL invoke did not return assistant.message or assistant.message_delta\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL implicit permission not ready after 6 invoke attempts\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL invoke returned terminal SSE error without assistant event\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL evidence incomplete\n' > /tmp/ghcp-hosted-agents-smoke-result
```

The marker file is authoritative. Do not invoke more tools after writing it.

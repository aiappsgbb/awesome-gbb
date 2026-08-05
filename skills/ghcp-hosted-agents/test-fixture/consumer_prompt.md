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

**Dual-scope instance RBAC is required before real inference.** A hosted
agent has two distinct identities. The **blueprint** identity (bound to the
agent definition) needs no data-plane role grants. The **instance** identity
(the per-version service principal the running agent presents when it calls
the model) MUST hold the `Foundry User` role
(`53ca6127-db72-4b80-b1b0-d745d6d5456d`) at BOTH the Foundry account scope
AND the Foundry project scope, or real model inference returns HTTP 401. The
earlier "implicit access, never grant" note was validated only against an
upstream echo agent that never called a model; it silently 401'd on live
inference. Step 3.5 below discovers the instance principal and creates both
assignments before Step 4 invokes; Step 5 revokes only those two assignments.
Do NOT grant any role to the blueprint identity, and do NOT grant at only one
scope (project-only and account-only both 401).

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
FAIL - do not attempt to work around it by re-running deploy. Instance-identity
role grants happen in Step 3.5 (after the version is active), not here. **The
deploy command above is the only deploy attempt.** On any failure, do not rerun
deploy, query Azure to discover replacement values, hardcode inventory, or
modify the azd env. Write the matching FAIL marker and stop.

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
import json
import os
import re
import time

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from pathlib import Path

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

    # Discover the INSTANCE (per-version) managed identity principal. This is
    # the identity that presents to the model at inference time and that must
    # receive Foundry User at both scopes in Step 3.5. The blueprint identity
    # is NOT this one and needs no grant. The exact field name on the version
    # object is the one live-CI-iterable assumption in this fixture: search the
    # full object recursively for a principal/object id, and also expose the
    # raw object for a REST fallback.
    version_obj = dict(version)
    Path("/tmp/ghcp-hosted-agents-version.json").write_text(
        json.dumps(version_obj, default=str), encoding="utf-8"
    )

    _GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                       r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
    _KEYS = ("principal_id", "principalId", "object_id", "objectId")

    def _find_principal(node):
        if isinstance(node, dict):
            for key in _KEYS:
                val = node.get(key)
                if isinstance(val, str) and _GUID.match(val):
                    return val
            identity = node.get("identity")
            if identity is not None:
                found = _find_principal(identity)
                if found:
                    return found
            for val in node.values():
                found = _find_principal(val)
                if found:
                    return found
        elif isinstance(node, list):
            for item in node:
                found = _find_principal(item)
                if found:
                    return found
        return None

    instance_principal = _find_principal(version_obj) or ""
    Path("/tmp/ghcp-hosted-agents-instance-principal").write_text(
        instance_principal, encoding="utf-8"
    )
    if instance_principal:
        record(f"INSTANCE_PRINCIPAL id={instance_principal} source=version-object")
    else:
        print("NOTE instance principal not on version object; Step 3.5 will "
              "attempt a REST fallback before granting")
```

Add `import json` and `import re` to the program's imports alongside the
existing `import os` / `import time`. Do not use `allow_preview=True`,
`project.beta.agents.patch_agent_details`, protocol version `"1.0.0"`/`"v1"`,
or a `Foundry-Features` preview header. A permission error during deploy or
the version check is a hard FAIL. The only retryable permission case is the
grant-propagation readiness envelope classified in Step 4.

## Step 3.5 - grant the instance identity Foundry User at both scopes

The instance principal discovered in Step 3 must hold `Foundry User`
(`53ca6127-db72-4b80-b1b0-d745d6d5456d`) at BOTH the Foundry account scope AND
the Foundry project scope before invocation. Project scope is the full project
ARM id from CI; account scope strips the trailing `/projects/<name>` segment.
Create both assignments now, before Step 4. The CI UAMI's ABAC condition
permits granting only this one role at the account and its descendants.

```bash
INSTANCE_PRINCIPAL="$(cat /tmp/ghcp-hosted-agents-instance-principal)"
if [ -z "$INSTANCE_PRINCIPAL" ]; then
  # REST fallback: read the agent version resource and scan for a principalId.
  agent_name="$(cat /tmp/ghcp-hosted-agents-agent-name)"
  INSTANCE_PRINCIPAL="$(az rest --method get \
    --url "${FOUNDRY_PROJECT_ENDPOINT%/}/assistants/${agent_name}/versions/1?api-version=2025-05-01" \
    --resource "https://ai.azure.com" 2>/dev/null \
    | jq -r '[.. | objects | (.principalId // .principal_id // .objectId // .object_id) | select(type=="string")] | first // empty')"
fi
if [ -z "$INSTANCE_PRINCIPAL" ]; then
  printf 'SMOKE_RESULT=FAIL could not discover hosted-agent instance principal\n' \
    > /tmp/ghcp-hosted-agents-smoke-result
  exit 1
fi
printf 'INSTANCE_PRINCIPAL id=%s\n' "$INSTANCE_PRINCIPAL" \
  >> /tmp/ghcp-hosted-agents-smoke-evidence

foundry_role="53ca6127-db72-4b80-b1b0-d745d6d5456d"
project_scope="$AZURE_AI_PROJECT_ID"
account_scope="${AZURE_AI_PROJECT_ID%/projects/*}"

az role assignment create \
  --role "$foundry_role" \
  --assignee-object-id "$INSTANCE_PRINCIPAL" \
  --assignee-principal-type ServicePrincipal \
  --scope "$account_scope" >/dev/null
printf 'ROLE_ASSIGNED scope=account\n' >> /tmp/ghcp-hosted-agents-smoke-evidence
printf 'ROLE_ASSIGNED scope=account\n'

az role assignment create \
  --role "$foundry_role" \
  --assignee-object-id "$INSTANCE_PRINCIPAL" \
  --assignee-principal-type ServicePrincipal \
  --scope "$AZURE_AI_PROJECT_ID" >/dev/null
printf 'ROLE_ASSIGNED scope=project\n' >> /tmp/ghcp-hosted-agents-smoke-evidence
printf 'ROLE_ASSIGNED scope=project\n'

echo "$INSTANCE_PRINCIPAL" > /tmp/ghcp-hosted-agents-instance-principal
```

Role-assignment propagation is not instant. Do NOT add a fixed long sleep
here - Step 4's bounded six-attempt invoke loop (15-second backoff) is the
propagation wait: an initial `model.call_failure` 401 / `transient_auth_error`
may appear before propagation completes, and the loop retries the same invoke
path until a recovered assistant event appears in the stream. Grant exactly
these two assignments and nothing else; grant to the instance principal only,
never the blueprint identity.

## Step 4 - invoke via `azd ai agent invoke` (single documented path)

Per SKILL.md § "Invoking the Agent", `azd ai agent invoke` is the primary
documented path on GA. Use only this path, with a bounded retry for the
grant-propagation readiness envelope (an initial `model.call_failure` 401 /
`transient_auth_error` that clears once the Step 3.5 assignments propagate).
The only retryable permission case is this exact immediate-post-active readiness envelope; every other permission failure is a hard FAIL. Capture
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
envelope_started = False
saw_transient_auth_info = False
provider_auth_terminal = False
unrelated_terminal_error = False
malformed_data = False

# Preserve SSE frame boundaries so an `event: done` payload is not mistaken
# for an ordinary untyped data event. HTTP status/header blocks are ignored.
frames = []
frame_event = None
frame_data = []
frame_invalid = False
raw_lines = Path(sys.argv[1]).read_text(
    encoding="utf-8", errors="replace"
).splitlines()
for line in [*raw_lines, ""]:
    if not line:
        if frame_event is not None or frame_data or frame_invalid:
            frames.append((frame_event, "\n".join(frame_data), frame_invalid))
        frame_event = None
        frame_data = []
        frame_invalid = False
    elif line.startswith("event:"):
        if frame_event is not None:
            frame_invalid = True
        frame_event = line[6:].strip()
        if not frame_event:
            frame_invalid = True
    elif line.startswith("data:"):
        frame_data.append(line[5:].lstrip())
    elif frame_event is not None or frame_data:
        frame_invalid = True

done_seen = False
for frame_event, payload, frame_invalid in frames:
    if frame_invalid or done_seen or not payload:
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
    if frame_event is not None:
        invocation_id = event.get("invocation_id")
        if (
            frame_event != "done"
            or not isinstance(invocation_id, str)
            or not invocation_id.strip()
            or not (success or provider_auth_terminal)
        ):
            malformed_data = True
            continue
        done_seen = True
        continue

    event_type = event.get("type")
    if not isinstance(event_type, str):
        malformed_data = True
        continue
    if provider_auth_terminal:
        if (
            not success
            and event_type in {"assistant.message", "assistant.message_delta"}
        ):
            success = True
        elif success and event_type in {"session.usage_info", "assistant.turn_end"}:
            pass
        else:
            unrelated_terminal_error = True
        continue
    if event_type in {"assistant.message", "assistant.message_delta"}:
        success = True
    elif event_type == "model.call_failure":
        data = event.get("data") or {}
        if not isinstance(data, dict):
            malformed_data = True
            continue
        error_message = data.get("errorMessage")
        if not isinstance(error_message, str):
            malformed_data = True
            continue
        if data.get("statusCode") == 401 and "PermissionDenied" in error_message:
            # The first event in the exact live readiness envelope names the
            # missing project-scoped Responses action and request path.
            anchored = (
                "Microsoft.CognitiveServices/accounts/OpenAI/responses/write"
                in error_message
                and "POST /openai/v1/responses" in error_message
            )
            if success:
                unrelated_terminal_error = True
            elif not envelope_started:
                if anchored:
                    envelope_started = True
                else:
                    unrelated_terminal_error = True
            # After the anchored first failure, subsequent 401
            # PermissionDenied model failures may interleave with retry info.
            elif anchored:
                unrelated_terminal_error = True
            else:
                pass
        else:
            unrelated_terminal_error = True
    elif event_type == "session.info":
        data = event.get("data")
        if not isinstance(data, dict):
            malformed_data = True
            continue
        message = data.get("message")
        if not isinstance(message, str):
            malformed_data = True
            continue
        if "transient_auth_error" in message:
            if envelope_started and not success:
                saw_transient_auth_info = True
            else:
                unrelated_terminal_error = True
    elif event_type == "error":
        message = event.get("message")
        if not isinstance(message, str):
            malformed_data = True
            continue
        if (
            "Authentication failed with provider" in message
            and "HTTP 401" in message
            and envelope_started
            and saw_transient_auth_info
            and not success
        ):
            provider_auth_terminal = True
        else:
            unrelated_terminal_error = True
    elif envelope_started:
        if event_type not in {"session.usage_info", "assistant.turn_end"}:
            unrelated_terminal_error = True

if malformed_data or unrelated_terminal_error:
    raise SystemExit(20)
if success:
    raise SystemExit(0 if not envelope_started or provider_auth_terminal else 20)
if provider_auth_terminal:
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
`transient_auth_error`) with six attempts and 15-second backoff - this is the
Step 3.5 grant-propagation window. A nonzero CLI exit or any other terminal
envelope is a hard FAIL. The Step 3.5 assignments are already in place; do not
add further role grants or re-grant here. The last exact raw response is
persisted to `/tmp/ghcp-hosted-agents-invoke.log`; the workflow snapshots it
under an attempt-specific filename before any retry and uploads both attempts.

## Step 5 - best-effort teardown

Read the agent name persisted in Step 2 and perform teardown in a bounded
300-second window. A failure or timeout here does NOT affect the PASS marker -
print one NOTE to stdout and continue to Step 6. Teardown also revokes the two
role assignments Step 3.5 created (and nothing else). The CI resource group is
periodically pruned of orphaned hosted-agent versions and ACR repositories by
a separate janitor.

```bash
agent_name="$(cat /tmp/ghcp-hosted-agents-agent-name)"
timeout 300 azd ai agent delete "$agent_name" --force --no-prompt \
  && printf 'AGENT_DELETED name=%s\n' "$agent_name" >> /tmp/ghcp-hosted-agents-smoke-evidence \
  || echo "NOTE best-effort teardown exceeded 300-second cap or encountered an error; CI janitor will prune orphaned resources"

# Best-effort revoke of only the two assignments Step 3.5 created.
INSTANCE_PRINCIPAL="$(cat /tmp/ghcp-hosted-agents-instance-principal 2>/dev/null)"
if [ -n "$INSTANCE_PRINCIPAL" ]; then
  foundry_role="53ca6127-db72-4b80-b1b0-d745d6d5456d"
  az role assignment delete --role "$foundry_role" \
    --assignee "$INSTANCE_PRINCIPAL" \
    --scope "${AZURE_AI_PROJECT_ID%/projects/*}" 2>/dev/null \
    && echo "NOTE revoked account-scope grant" || true
  az role assignment delete --role "$foundry_role" \
    --assignee "$INSTANCE_PRINCIPAL" \
    --scope "$AZURE_AI_PROJECT_ID" 2>/dev/null \
    && echo "NOTE revoked project-scope grant" || true
fi
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
    r"INSTANCE_PRINCIPAL id=\S+",
    r"ROLE_ASSIGNED scope=account",
    r"ROLE_ASSIGNED scope=project",
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
printf 'SMOKE_RESULT=FAIL could not discover hosted-agent instance principal\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL role assignment create failed for instance identity\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL agent version never reached active\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL protocol version mismatch - expected invocations 2.0.0\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL invoke command exited non-zero\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL invoke did not return assistant.message or assistant.message_delta\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL implicit permission not ready after 6 invoke attempts\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL invoke returned terminal SSE error without assistant event\n' > /tmp/ghcp-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL evidence incomplete\n' > /tmp/ghcp-hosted-agents-smoke-result
```

The marker file is authoritative. Do not invoke more tools after writing it.

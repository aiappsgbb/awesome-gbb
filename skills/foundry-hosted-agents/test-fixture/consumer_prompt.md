# Customer goal - `foundry-hosted-agents` GA smoke

Execute a live Microsoft Foundry hosted-agent GA smoke against the CI
project. This is an execution test, not a catalog-inspection task. Follow
the exact contract below; do not browse the repository or load the full
SKILL.md into context.

## Step -1 - acknowledge the skill contract

Your first Bash action must be:

```bash
echo "skills/foundry-hosted-agents/SKILL.md"
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
  /tmp/foundry-hosted-agents-smoke-result \
  /tmp/foundry-hosted-agents-smoke-evidence \
  /tmp/foundry-hosted-agents-agent-name
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
echo "AZURE_AI_PROJECT_ID=${AZURE_AI_PROJECT_ID:+set}"
echo "ACR_LOGIN_SERVER=${ACR_LOGIN_SERVER:+set}"
test -n "${AZURE_CLIENT_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL missing AZURE_CLIENT_ID\n' > /tmp/foundry-hosted-agents-smoke-result
  exit 1
}
test -n "${AZURE_TENANT_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL missing AZURE_TENANT_ID\n' > /tmp/foundry-hosted-agents-smoke-result
  exit 1
}
test -n "${AZURE_SUBSCRIPTION_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL missing AZURE_SUBSCRIPTION_ID\n' > /tmp/foundry-hosted-agents-smoke-result
  exit 1
}
test -n "${FOUNDRY_PROJECT_ENDPOINT:-}" || {
  printf 'SMOKE_RESULT=FAIL missing FOUNDRY_PROJECT_ENDPOINT\n' > /tmp/foundry-hosted-agents-smoke-result
  exit 1
}
test -n "${AZURE_AI_PROJECT_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL missing AZURE_AI_PROJECT_ID\n' > /tmp/foundry-hosted-agents-smoke-result
  exit 1
}
test -n "${ACR_LOGIN_SERVER:-}" || {
  printf 'SMOKE_RESULT=FAIL missing ACR_LOGIN_SERVER\n' > /tmp/foundry-hosted-agents-smoke-result
  exit 1
}
if [[ "$ACR_LOGIN_SERVER" == *"://"* \
   || "$ACR_LOGIN_SERVER" == */* \
   || "$ACR_LOGIN_SERVER" != *.azurecr.io ]]; then
  printf 'SMOKE_RESULT=FAIL malformed ACR_LOGIN_SERVER\n' > /tmp/foundry-hosted-agents-smoke-result
  exit 1
fi
az account show --output table || echo "(az cache not inherited - relying on DefaultAzureCredential)"
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
run `azd provision`, `az group create`, or anything that provisions a new
Foundry project or registry. Hosted agents run on
Foundry-managed, per-session sandboxes - there is no Container Apps
environment, no ACA app, and nothing else to provision for this fixture.

**No agent role grant.** Per the skill's GA identity guidance, the hosted
agent's own Entra identity has implicit access to model inferencing and
session storage by default. Do NOT run any `az role assignment create`
against the agent's identity, and do NOT expect one to be necessary. If
any step returns a permission error, that is a hard FAIL, not something to
route around with an ad hoc role grant.

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
  "$microsoft_foundry_version" >> /tmp/foundry-hosted-agents-smoke-evidence
printf 'AZD_EXTENSION_VERSION id=microsoft.foundry installedVersion=%s\n' \
  "$microsoft_foundry_version"
printf 'AZD_EXTENSION_VERSION id=azure.ai.agents installedVersion=%s\n' \
  "$agents_extension_version" >> /tmp/foundry-hosted-agents-smoke-evidence
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
`/tmp/foundry-hosted-agents-ga-smoke.sh`, then run it once:

```bash
#!/usr/bin/env bash
set -euo pipefail

evidence="/tmp/foundry-hosted-agents-smoke-evidence"

record() {
  printf '%s\n' "$1" >>"$evidence"
  printf '%s\n' "$1"
}

suffix="$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')"
agent_name="ci-smoke-ha-${suffix}"
work_dir="/tmp/foundry-hosted-agents-${suffix}"
mkdir -p "$work_dir"

# Copy the canonical reference files verbatim - do NOT hand-author these
# from training-data memory. SKILL.md's references/ directory is the
# single source of truth.
repo_root="${GITHUB_WORKSPACE:-$PWD}"
skill_refs="$repo_root/skills/foundry-hosted-agents/references"
cp "$skill_refs/docker/Dockerfile" "$work_dir/Dockerfile"
cp "$skill_refs/python/container.py" "$work_dir/container.py"
cp "$skill_refs/python/pyproject.toml" "$work_dir/pyproject.toml"
cp "$skill_refs/yaml/azure.yaml" "$work_dir/azure.yaml"
printf 'You are a customer-support triage assistant.\n' > "$work_dir/copilot-instructions.md"

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
        > /tmp/foundry-hosted-agents-smoke-result
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
echo "$agent_name" > /tmp/foundry-hosted-agents-agent-name
```

```bash
bash /tmp/foundry-hosted-agents-ga-smoke.sh
```

If `azd deploy` fails with a permission/authorization error, that is a hard
FAIL (see the "No agent role grant" note above) - do not attempt to work
around it with a manual role assignment. **The deploy command above is the
only deploy attempt.** On any failure, do not rerun deploy, query Azure to
discover replacement values, hardcode inventory, or modify the azd env.
Write the matching FAIL marker and stop.

## Step 3 - GA SDK hard checks (deterministic, no preview surfaces)

Create an isolated virtual environment and install the bounded stable stack:

```bash
python3 -m venv /tmp/foundry-hosted-agents-venv
/tmp/foundry-hosted-agents-venv/bin/pip install --quiet \
  "azure-ai-projects~=2.3.0" \
  "azure-identity~=1.25.3"
```

Use a Bash heredoc to write the following program to
`/tmp/foundry-hosted-agents-smoke.py`, then run it once with
`/tmp/foundry-hosted-agents-venv/bin/python`:

```python
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

evidence_path = "/tmp/foundry-hosted-agents-smoke-evidence"


def record(message: str) -> None:
    print(message)
    with open(evidence_path, "a", encoding="utf-8") as evidence:
        evidence.write(f"{message}\n")


with open("/tmp/foundry-hosted-agents-agent-name", encoding="utf-8") as f:
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
        p["protocol"] == "responses" and p["version"] == "2.0.0"
        for p in protocol_versions
    ), f"expected responses protocol 2.0.0, got {protocol_versions}"
    record(f"AGENT_VERSION_ACTIVE name={agent_name} protocol=responses/2.0.0")

    # Stable update_details - not the removed preview patch_agent_details.
    project.agents.update_details(
        agent_name=agent_name,
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
    record(f"UPDATE_DETAILS_OK name={agent_name} version=1 traffic=100")

    # Stable GA Responses invoke - no allow_preview, no preview header.
    openai_client = project.get_openai_client(agent_name=agent_name)
    response = None
    last_error = None
    for attempt in range(6):
        try:
            response = openai_client.responses.create(
                input=(
                    "Classify this message into exactly one label - "
                    "billing, technical, or account - and reply with "
                    "only that single word: "
                    "'My invoice this month is double what I expected.'"
                ),
                stream=False,
            )
            break
        except Exception as exc:  # noqa: BLE001 - bounded cold-start retry
            last_error = exc
            time.sleep(10)
    if response is None:
        raise RuntimeError(f"invoke never succeeded: {last_error}")

    label = response.output_text.strip().strip(".").lower()
    assert label in {"billing", "technical", "account"}, (
        f"expected exactly one of billing/technical/account, got {label!r}"
    )
    record(f"INVOKE_LABEL label={label}")
```

Do not use `allow_preview=True`, `project.beta.agents.patch_agent_details`,
`AgentEndpoint` (the old class - use `AgentEndpointConfig`), a
`Foundry-Features` preview header, or protocol version `"1.0.0"`/`"v1"`.
A permission error at any step (`PermissionDenied`, 403) is a hard FAIL -
do not retry it as if it were a transient cold-start error, and do not
attempt a manual role assignment to work around it.

## Step 4 - best-effort teardown

Read the agent name persisted in Step 2 and perform teardown in a bounded
5-minute window. A failure or timeout here does NOT affect the PASS marker -
print one NOTE to stdout and continue to Step 5. The CI resource group is
periodically pruned of orphaned hosted-agent versions and ACR repositories
by a separate janitor.

Write the following teardown script to `/tmp/foundry-hosted-agents-teardown.py`:

```python
#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

evidence = Path("/tmp/foundry-hosted-agents-smoke-evidence")
agent_name_file = Path("/tmp/foundry-hosted-agents-agent-name")


def note(message: str) -> None:
    print(message)
    with evidence.open("a", encoding="utf-8") as fp:
        fp.write(f"{message}\n")


if not agent_name_file.exists():
    note("NOTE teardown skipped: agent name file not found")
    sys.exit(0)

agent_name = agent_name_file.read_text(encoding="utf-8").strip()

# Best-effort agent delete using stable SDK with force=True.
try:
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    with DefaultAzureCredential() as credential, AIProjectClient(
        endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"], credential=credential
    ) as project:
        project.agents.delete(agent_name=agent_name, force=True)
        note(f"AGENT_DELETED name={agent_name}")
except Exception as exc:  # noqa: BLE001 - teardown is best-effort
    note(f"NOTE agent delete best-effort failure: {exc}")

# Best-effort ACR repository delete. The provider resolves the registry for
# deploy; ACR_LOGIN_SERVER is only an optional cleanup hint.
acr_login_server = os.environ.get("ACR_LOGIN_SERVER", "").strip()
if not acr_login_server:
    note("NOTE ACR repository cleanup skipped: ACR_LOGIN_SERVER not set")
else:
    try:
        acr_name = acr_login_server.split(".")[0]
        result = subprocess.run(
            ["az", "acr", "repository", "delete",
             "--name", acr_name,
             "--repository", agent_name,
             "--yes"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            note(f"ACR_REPO_DELETED name={agent_name}")
        else:
            note(f"NOTE ACR repository delete best-effort failure: {result.stderr.strip()}")
    except Exception as exc:  # noqa: BLE001 - teardown is best-effort
        note(f"NOTE ACR repository delete best-effort failure: {exc}")
```

Then run it with a 5-minute cap:

```bash
timeout 300 /tmp/foundry-hosted-agents-venv/bin/python3 /tmp/foundry-hosted-agents-teardown.py \
  || echo "NOTE best-effort teardown exceeded 5-minute cap or encountered an error; CI janitor will prune orphaned resources"
```

## Step 5 - Marker contract

After the invoke check passes, verify the evidence file contains every
required success record below (teardown records are best-effort and not
checked here):

```bash
python3 - <<'PY'
from pathlib import Path
import re

lines = Path("/tmp/foundry-hosted-agents-smoke-evidence").read_text(
    encoding="utf-8"
).splitlines()
required_patterns = (
    r"AZD_EXTENSION_VERSION id=microsoft\.foundry installedVersion=\S+",
    r"AZD_EXTENSION_VERSION id=azure\.ai\.agents installedVersion=\S+",
    r"AZD_ENV_CONTRACT_OK",
    r"AZD_DEPLOY_ATTEMPT count=1",
    r"AZD_DEPLOY_SUCCEEDED name=ci-smoke-ha-[0-9a-f]{8}",
    r"AGENT_VERSION_ACTIVE name=ci-smoke-ha-[0-9a-f]{8} protocol=responses/2\.0\.0",
    r"UPDATE_DETAILS_OK name=ci-smoke-ha-[0-9a-f]{8} version=1 traffic=100",
    r"INVOKE_LABEL label=(billing|technical|account)",
)
for pattern in required_patterns:
    assert any(re.fullmatch(pattern, line) for line in lines), (pattern, lines)
attempts = [line for line in lines if line.startswith("AZD_DEPLOY_ATTEMPT ")]
assert attempts == ["AZD_DEPLOY_ATTEMPT count=1"], attempts
PY
```

Only after that check succeeds, your final Bash action is:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-hosted-agents-smoke-result
```

If teardown (Step 4) left a `NOTE` line in the evidence
file, that does NOT block PASS - teardown is best-effort (5-minute cap).
The CI resource group is periodically pruned of orphaned hosted-agent
versions and ACR repositories by a separate janitor.

If a required step fails, choose exactly one matching command below as your
final Bash action:

```bash
printf 'SMOKE_RESULT=FAIL missing AZURE_CLIENT_ID\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL missing AZURE_TENANT_ID\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL missing AZURE_SUBSCRIPTION_ID\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL missing FOUNDRY_PROJECT_ENDPOINT\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL missing AZURE_AI_PROJECT_ID\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL missing ACR_LOGIN_SERVER\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL malformed ACR_LOGIN_SERVER\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL azd auth login failed\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL microsoft.foundry or azure.ai.agents extension not installed\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL azd env contract incomplete\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL azd deploy failed\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL permission denied - agent identity should have implicit access by default\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL agent version never reached active\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL protocol version mismatch - expected responses 2.0.0\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL update_details failed\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL invoke never returned a valid label\n' > /tmp/foundry-hosted-agents-smoke-result
printf 'SMOKE_RESULT=FAIL evidence incomplete\n' > /tmp/foundry-hosted-agents-smoke-result
```

The marker file is authoritative. Do not invoke more tools after writing it.

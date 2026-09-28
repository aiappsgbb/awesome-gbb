# Customer goal - `foundry-toolbox` GA smoke

Execute a live Microsoft Foundry Toolbox smoke against the CI project. This is
an execution test, not a catalog-inspection task. Follow the exact API contract
below; do not browse the repository or load the full SKILL.md into context.

**Coverage:** this baseline retains SDK 2.4 / MAF 1.13. It does not certify the
additive A2A 1.0 management path, tuned search/pinning, Prompt preview bridge,
Skills or private File Search. Those need the separately approved cases in
`service_acceptance.md`; do not upgrade this runtime implicitly.

## Step -1 - acknowledge the skill contract

Your first Bash action must be:

```bash
echo "skills/foundry-toolbox/SKILL.md"
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
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
az account show --output table || echo "(az cache not inherited - relying on DefaultAzureCredential)"
azd auth login \
  --federated-credential-provider github \
  --client-id "$AZURE_CLIENT_ID" \
  --tenant-id "$AZURE_TENANT_ID"
```

Only assert that the four environment variables are non-empty. Do not compare
subscription IDs, decode tokens, or gate on Azure CLI cache visibility. If an
environment variable is empty, write the FAIL marker from the final step with
the exact missing variable name and stop. `azd auth login` is the explicit azd
authentication gate; if it fails, use the matching final-step marker.

## Step 1 - execute the azd and GA SDK Toolbox contracts

Execute each script once. Never edit tracked source or change the evidence
destination to recover from a permission failure. Both scripts and the final
validator use **the same** `/tmp/foundry-toolbox-smoke-evidence` file, which
the workflow archives. A scratch copy is not equivalent. If access fails,
write the FAIL marker if permitted and stop before creating replacements.
Keep any earlier run with missing IDs/cleanup receipts explicitly unverified;
do not infer deletion from a PASS marker or clean up an earlier run's names.

The Copilot CLI shell-tool permission gate rejects file creation OUTSIDE
`$GITHUB_WORKSPACE`, even with `--allow-all-tools` (a heredoc write to `/tmp`
fails with "Permission denied and could not request permission from user"), so
every program you author through a Bash heredoc must live under a
workspace-local scratch directory. Shell variables do not persist across
separate Copilot tool calls, so always spell out the explicit
`${GITHUB_WORKSPACE}` path in each command. Create the scratch directory first:

```bash
set -euo pipefail
mkdir -p "${GITHUB_WORKSPACE}/.scratch/foundry-toolbox"
test ! -s /tmp/foundry-toolbox-smoke-evidence
touch /tmp/foundry-toolbox-smoke-evidence
test -r /tmp/foundry-toolbox-smoke-evidence
test -w /tmp/foundry-toolbox-smoke-evidence
```

First, run the exact service-target and standalone-file shapes documented by
the skill. Use a Bash heredoc to write this script to
`${GITHUB_WORKSPACE}/.scratch/foundry-toolbox/foundry-toolbox-azd-smoke.sh`,
then run it once:

```bash
#!/usr/bin/env bash
set -euo pipefail

evidence="/tmp/foundry-toolbox-smoke-evidence"
if [[ -s "$evidence" ]]; then
  echo "FAIL existing evidence: do not replay the azd smoke"
  exit 1
fi
: >"$evidence"

record() {
  printf '%s\n' "$1" | tee -a "$evidence"
}

suffix="$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')"
service_name="ci-smoke-azdsvc-${suffix}"
cli_name="ci-smoke-azdcli-${suffix}"
work_dir="/tmp/foundry-toolbox-azd-${suffix}"
mkdir -p "$work_dir"

cat >"$work_dir/azure.yaml" <<YAML
name: foundry-toolbox-smoke
services:
  ${service_name}:
    host: azure.ai.toolbox
    description: CI azd service-target smoke.
    tools:
      - type: code_interpreter
YAML

cat >"$work_dir/toolbox.yaml" <<'YAML'
description: CI standalone CLI smoke.
tools:
  - type: code_interpreter
YAML

cleanup() {
  status=$?
  set +e
  for toolbox_name in "$cli_name" "$service_name"; do
    delete_log="/tmp/${toolbox_name}-delete.log"
    azd ai toolbox delete "$toolbox_name" \
      --force \
      --no-prompt >"$delete_log" 2>&1
    delete_status=$?
    if [[ $delete_status -ne 0 ]]; then
      echo "NOTE azd Toolbox delete failed name=${toolbox_name} status=${delete_status}"
    fi
  done
  rm -rf "$work_dir"
  trap - EXIT
  exit "$status"
}
trap cleanup EXIT

azd extension install microsoft.foundry --version 1.0.0-beta.1
azd ai project set "$FOUNDRY_PROJECT_ENDPOINT" --no-prompt
azd ai project show

(
  cd "$work_dir"
  azd env new "$service_name" --no-prompt
  azd env set FOUNDRY_PROJECT_ENDPOINT "$FOUNDRY_PROJECT_ENDPOINT"
  azd deploy "$service_name" --no-prompt
)
azd ai toolbox show "$service_name" --output json
record "AZD_SERVICE_CREATED name=${service_name}"

azd ai toolbox create "$cli_name" \
  --from-file "$work_dir/toolbox.yaml" \
  --no-prompt \
  --output json
azd ai toolbox show "$cli_name" --output json
record "AZD_CLI_CREATED name=${cli_name}"
```

```bash
bash "${GITHUB_WORKSPACE}/.scratch/foundry-toolbox/foundry-toolbox-azd-smoke.sh"
```

After that script exits `0`, both azd Toolboxes have been cleaned up
best-effort and any deletion trouble is transcript-only. Create an isolated
workspace-local virtual environment and install the bounded Python stack.
Activation avoids invoking a `/tmp` interpreter through the shell permission
gate; it does not move the evidence file:

```bash
set -euo pipefail
python3 -m venv "${GITHUB_WORKSPACE}/.scratch/foundry-toolbox/venv"
source "${GITHUB_WORKSPACE}/.scratch/foundry-toolbox/venv/bin/activate"
python -m pip install --quiet \
  "azure-ai-projects~=2.4.0" \
  "azure-identity~=1.25.3" \
  "agent-framework~=1.13.0" \
  "agent-framework-foundry-hosting==1.0.0b260730" \
  "mcp~=1.29.0"
```

Use a Bash heredoc to write the following program to
`${GITHUB_WORKSPACE}/.scratch/foundry-toolbox/foundry-toolbox-smoke.py`, then
run it once with the venv interpreter:

```python
import asyncio
import os
import uuid

from agent_framework_foundry_hosting import FoundryToolbox
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    CodeInterpreterToolboxTool,
    ToolSearchToolboxTool,
)
from azure.identity import DefaultAzureCredential


evidence_path = "/tmp/foundry-toolbox-smoke-evidence"


def record(message: str) -> None:
    print(message)
    with open(evidence_path, "a", encoding="utf-8") as evidence:
        evidence.write(f"{message}\n")


async def verify_functions(
    credential: DefaultAzureCredential,
    toolbox_url: str,
    toolbox_name: str,
) -> None:
    async with FoundryToolbox(
        credential,
        url=toolbox_url,
        name=toolbox_name,
    ) as toolbox:
        names = {
            getattr(function, "name", None)
            or getattr(function, "__name__", None)
            for function in toolbox.functions
        }
        names.discard(None)
        assert {"tool_search", "call_tool"} <= names, names
        record(f"TOOL_SEARCH_FUNCTIONS names={','.join(sorted(names))}")


project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
toolbox_name = f"ci-smoke-tbx-{uuid.uuid4().hex[:8]}"

with (
    DefaultAzureCredential() as credential,
    AIProjectClient(
        endpoint=project_endpoint,
        credential=credential,
    ) as project,
):
    created = project.toolboxes.create_version(
        name=toolbox_name,
        description="CI stable Tool Search smoke",
        tools=[
            ToolSearchToolboxTool(name="tool-search"),
            CodeInterpreterToolboxTool(name="code-interpreter"),
        ],
    )
    try:
        assert created.name == toolbox_name
        assert created.version
        record(
            f"TOOL_SEARCH_CREATED name={created.name} "
            f"version={created.version}"
        )

        fetched = project.toolboxes.get_version(
            toolbox_name,
            created.version,
        )
        assert fetched.name == created.name
        assert fetched.version == created.version
        record(
            f"TOOLBOX_RETRIEVED name={fetched.name} "
            f"version={fetched.version}"
        )

        toolbox_url = (
            f"{project_endpoint.rstrip('/')}/toolboxes/{toolbox_name}"
            f"/versions/{created.version}/mcp?api-version=v1"
        )
        asyncio.run(
            verify_functions(
                credential,
                toolbox_url,
                toolbox_name,
            )
        )
    finally:
        try:
            project.toolboxes.delete(toolbox_name)
        except Exception as exc:
            print(
                f"NOTE Toolbox delete failed name={toolbox_name} "
                f"error_type={type(exc).__name__}"
            )
```

Run it once:

```bash
set -euo pipefail
source "${GITHUB_WORKSPACE}/.scratch/foundry-toolbox/venv/bin/activate"
python "${GITHUB_WORKSPACE}/.scratch/foundry-toolbox/foundry-toolbox-smoke.py"
```

Every management call in this Python smoke must stay under stable
`project.toolboxes`. `project.beta.toolboxes` is forbidden; if stable
`project.toolboxes` rejects the Tool Search payload, stop and fail. Beta-only
acceptance is a hard failure and triggers rollback rather than any retry under
beta. Do not use generic Agent tool classes, a
`create_toolbox_version` method, `allow_preview=True`, raw REST, or any preview
feature header. Keep the Python Toolbox deletion inside this same smoke
program, but make it best-effort: once `create_version` succeeds, run the
get/assert/verify steps inside a `try` whose `finally` attempts
`project.toolboxes.delete(toolbox_name)`, so a raised assertion or meta-tool
verification failure still triggers cleanup instead of leaking the toolbox.
Catch deletion exceptions, print exactly one transcript-only `NOTE` sanitized
to the toolbox name and `type(exc).__name__`, and never append a deletion
sidecar record, re-raise from the cleanup handler, or replace completed hard
proof (or a propagating get/assert/verify failure) with a cleanup-only
failure.

## Step 2 - write the deterministic result marker

After both azd Toolboxes and the Python Toolbox have been cleaned up
best-effort, execute this final block unchanged. It reads back the canonical
archive destination, requires **five TOTAL records (two azd plus three SDK)**,
and only then writes PASS. A cleanup NOTE remains a cleanup limitation, not
proof of absence. Do not relocate evidence, rerun creation, or independently
write PASS if any assertion or file operation fails.

```bash
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import hashlib
import re

marker = Path("/tmp/foundry-toolbox-smoke-result")
marker.write_text("SMOKE_RESULT=FAIL evidence incomplete\n", encoding="utf-8")
evidence = Path("/tmp/foundry-toolbox-smoke-evidence")
raw = evidence.read_bytes()
lines = raw.decode("utf-8").splitlines()
patterns = (
    r"AZD_SERVICE_CREATED name=ci-smoke-azdsvc-[0-9a-f]{8}",
    r"AZD_CLI_CREATED name=ci-smoke-azdcli-[0-9a-f]{8}",
    r"TOOL_SEARCH_CREATED name=ci-smoke-tbx-[0-9a-f]{8} version=\S+",
    r"TOOLBOX_RETRIEVED name=ci-smoke-tbx-[0-9a-f]{8} version=\S+",
    r"TOOL_SEARCH_FUNCTIONS names=.+",
)
assert len(lines) == len(patterns) == 5
for pattern, line in zip(patterns, lines):
    assert re.fullmatch(pattern, line), "Missing or out-of-order hard-success record"
assert lines[2].split(" ", 1)[1] == lines[3].split(" ", 1)[1], "SDK identity/version mismatch"
names = set(lines[4].split("names=", 1)[1].split(","))
assert {"tool_search", "call_tool"} <= names, "Tool Search meta-tools missing"
assert evidence.read_bytes() == raw, "Evidence changed during validation"
print(f"TOOLBOX_ARCHIVE_EVIDENCE_VERIFIED records=5 sha256={hashlib.sha256(raw).hexdigest()}")
marker.write_text("SMOKE_RESULT=PASS\n", encoding="utf-8")
PY
```

This validator is the only success-marker writer. Its canonical file remains
in place for workflow upload. Do not invoke another tool after it succeeds.

If a required step fails, choose exactly one matching command below as your
final Bash action:

```bash
printf 'SMOKE_RESULT=FAIL missing AZURE_CLIENT_ID\n' > /tmp/foundry-toolbox-smoke-result
printf 'SMOKE_RESULT=FAIL missing AZURE_TENANT_ID\n' > /tmp/foundry-toolbox-smoke-result
printf 'SMOKE_RESULT=FAIL missing AZURE_SUBSCRIPTION_ID\n' > /tmp/foundry-toolbox-smoke-result
printf 'SMOKE_RESULT=FAIL missing FOUNDRY_PROJECT_ENDPOINT\n' > /tmp/foundry-toolbox-smoke-result
printf 'SMOKE_RESULT=FAIL azd auth login failed\n' > /tmp/foundry-toolbox-smoke-result
printf 'SMOKE_RESULT=FAIL azd Toolbox smoke failed\n' > /tmp/foundry-toolbox-smoke-result
printf 'SMOKE_RESULT=FAIL package install failed\n' > /tmp/foundry-toolbox-smoke-result
printf 'SMOKE_RESULT=FAIL create_version failed\n' > /tmp/foundry-toolbox-smoke-result
printf 'SMOKE_RESULT=FAIL get_version failed\n' > /tmp/foundry-toolbox-smoke-result
printf 'SMOKE_RESULT=FAIL FoundryToolbox connect failed\n' > /tmp/foundry-toolbox-smoke-result
printf 'SMOKE_RESULT=FAIL Tool Search meta-tools missing\n' > /tmp/foundry-toolbox-smoke-result
printf 'SMOKE_RESULT=FAIL evidence incomplete\n' > /tmp/foundry-toolbox-smoke-result
```

The marker file is authoritative. Do not invoke more tools after writing it.

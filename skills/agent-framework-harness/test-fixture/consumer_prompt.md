# Agent Framework Harness live Foundry smoke

This is an execution smoke. Follow these steps directly; do not inspect the
catalog or redesign the task. Do not view the full SKILL.md.

## Step -1 — acknowledge the contract

Your first Bash action must be this lightweight audit acknowledgement:

```bash
echo "skills/agent-framework-harness/SKILL.md"
```

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You ARE
the running Copilot CLI process. Never run `copilot -p`, `copilot --version`,
install Copilot, or make any other `copilot` invocation. Never write or
overwrite a transcript file. The workflow's outer `tee` already captures
your output; execute these steps directly.

## Step 0 — verify the read-only CI environment

Before starting, remove only these three targeted paths; use no wildcard:

```bash
rm -f /tmp/agent-framework-harness-smoke-result
rm -f /tmp/agent-framework-harness-oidc-token
rm -rf /tmp/agent-framework-harness-venv

echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
echo "FOUNDRY_MODEL_DEPLOYMENT=${FOUNDRY_MODEL_DEPLOYMENT:+set}"
if test -n "${ACTIONS_ID_TOKEN_REQUEST_URL:-}"; then
  echo "ACTIONS_ID_TOKEN_REQUEST_URL=set"
else
  echo "ACTIONS_ID_TOKEN_REQUEST_URL=unset"
fi
if test -n "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:-}"; then
  echo "ACTIONS_ID_TOKEN_REQUEST_TOKEN=set"
else
  echo "ACTIONS_ID_TOKEN_REQUEST_TOKEN=unset"
fi

test -n "${AZURE_CLIENT_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL %s\n' "missing AZURE_CLIENT_ID" > /tmp/agent-framework-harness-smoke-result
  exit 1
}
test -n "${AZURE_TENANT_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL %s\n' "missing AZURE_TENANT_ID" > /tmp/agent-framework-harness-smoke-result
  exit 1
}
test -n "${AZURE_SUBSCRIPTION_ID:-}" || {
  printf 'SMOKE_RESULT=FAIL %s\n' "missing AZURE_SUBSCRIPTION_ID" > /tmp/agent-framework-harness-smoke-result
  exit 1
}
test -n "${FOUNDRY_PROJECT_ENDPOINT:-}" || {
  printf 'SMOKE_RESULT=FAIL %s\n' "missing FOUNDRY_PROJECT_ENDPOINT" > /tmp/agent-framework-harness-smoke-result
  exit 1
}
test -n "${FOUNDRY_MODEL_DEPLOYMENT:-}" || {
  printf 'SMOKE_RESULT=FAIL %s\n' "missing FOUNDRY_MODEL_DEPLOYMENT" > /tmp/agent-framework-harness-smoke-result
  exit 1
}
test -n "${ACTIONS_ID_TOKEN_REQUEST_URL:-}" || {
  printf 'SMOKE_RESULT=FAIL %s\n' "missing ACTIONS_ID_TOKEN_REQUEST_URL" > /tmp/agent-framework-harness-smoke-result
  exit 1
}
test -n "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:-}" || {
  printf 'SMOKE_RESULT=FAIL %s\n' "missing ACTIONS_ID_TOKEN_REQUEST_TOKEN" > /tmp/agent-framework-harness-smoke-result
  exit 1
}

az account show --output table || echo "(az cache not inherited; DefaultAzureCredential workload identity is configured in Step 1)"
```

Use existence checks only. Do not compare subscription IDs, decode tokens,
inspect claims, print the OIDC request token or response, or validate GUID
shapes. Do not run `az login` or `azd`, regrant RBAC, deploy or provision
resources, install Azure CLI or system tools, hunt the filesystem for tools,
or start a server. The shared Foundry project and model are pre-provisioned
and read-only. Make one model call only.

## Step 1 — run the canonical harness once

Run from the repository root. Copilot Bash actions use fresh shells, so you
MUST execute this complete fenced block in one Bash tool call without
splitting it. In particular, do not separate the exports, OIDC exchange, or
Python heredoc into different Bash actions.

```bash
set -euo pipefail
set +x

TOKEN_FILE=/tmp/agent-framework-harness-oidc-token
rm -f "$TOKEN_FILE"
trap 'rm -f /tmp/agent-framework-harness-oidc-token' EXIT

test -n "${ACTIONS_ID_TOKEN_REQUEST_URL:-}" || {
  printf 'SMOKE_RESULT=FAIL %s\n' "missing ACTIONS_ID_TOKEN_REQUEST_URL" > /tmp/agent-framework-harness-smoke-result
  exit 1
}
test -n "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:-}" || {
  printf 'SMOKE_RESULT=FAIL %s\n' "missing ACTIONS_ID_TOKEN_REQUEST_TOKEN" > /tmp/agent-framework-harness-smoke-result
  exit 1
}

python3 -m venv /tmp/agent-framework-harness-venv
/tmp/agent-framework-harness-venv/bin/pip install --quiet \
  "agent-framework-core~=1.13.0" \
  "agent-framework-foundry~=1.10.4" \
  "agent-framework-foundry-hosting==1.0.0b260730" \
  "azure-identity~=1.25.3"

OIDC_REQUEST_URL="${ACTIONS_ID_TOKEN_REQUEST_URL}&audience=api%3A%2F%2FAzureADTokenExchange"
curl --fail --silent --show-error \
  --header "Authorization: Bearer ${ACTIONS_ID_TOKEN_REQUEST_TOKEN}" \
  "$OIDC_REQUEST_URL" |
  /tmp/agent-framework-harness-venv/bin/python -c '
import json
import os
import sys

value = json.load(sys.stdin).get("value")
if not isinstance(value, str) or not value:
    raise SystemExit("OIDC response missing value")
fd = os.open(
    "/tmp/agent-framework-harness-oidc-token",
    os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
    0o600,
)
with os.fdopen(fd, "w") as token_file:
    token_file.write(value)
'
chmod 600 "$TOKEN_FILE"

export AZURE_FEDERATED_TOKEN_FILE="$TOKEN_FILE"
export AZURE_AI_MODEL_DEPLOYMENT_NAME="$FOUNDRY_MODEL_DEPLOYMENT"
echo "AZURE_AI_MODEL_DEPLOYMENT_NAME=${AZURE_AI_MODEL_DEPLOYMENT_NAME:+set}"

/tmp/agent-framework-harness-venv/bin/python - <<'PY'
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from agent_framework import Agent, AgentSession
from agent_framework_foundry_hosting import ResponsesHostServer

reference_dir = Path(
    "skills/agent-framework-harness/references/python"
).resolve()
sys.path.insert(0, str(reference_dir))

from hosted_harness import build_agent, build_server


async def main() -> None:
    print("HARNESS_REFERENCE_IMPORT_OK")
    agent = build_agent()
    assert isinstance(agent, Agent)
    assert agent.default_options["store"] is False
    print("HARNESS_AGENT_CONSTRUCTED")

    server = build_server(agent)
    assert isinstance(server, ResponsesHostServer)
    print("HOSTING_ADAPTER_CONSTRUCTED")

    session = agent.create_session()
    assert isinstance(session, AgentSession)
    response = await agent.run(
        "Reply with exactly HARNESS_LIVE_OK.",
        session=session,
    )
    assert "HARNESS_LIVE_OK" in response.text
    print("HARNESS_LIVE_RESPONSE_OK")


asyncio.run(main())
PY
```

Do not install the `agent-framework` meta-package or tools package. Import
`build_agent` and `build_server` only from the canonical `hosted_harness`
reference; never copy or redefine them. Never call `server.run()`. Do not
create, delete, or tear down resources.

## Step 2 — write the deterministic result marker

The marker file is authoritative; the run is incomplete until it exists.
Never merely mention the marker token in assistant prose. On any failure,
your final Bash action must write a concise reason and stop:

```bash
printf 'SMOKE_RESULT=FAIL %s\n' "concise failure reason" > /tmp/agent-framework-harness-smoke-result
```

Only after every assertion and the live call succeed, your FINAL Bash tool
action must write exactly one line with no extra bytes. Do not emit assistant
prose after this action:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/agent-framework-harness-smoke-result
```

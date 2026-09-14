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

The workflow creates a private Azure CLI profile before `azure/login@v2`.
Use that already-authenticated identity through the SDK; do not read profile
files or request identity tokens manually.

Before starting, remove only these two targeted paths; use no wildcard:

```bash
rm -f /tmp/agent-framework-harness-smoke-result
rm -rf /tmp/agent-framework-harness-venv

echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
echo "FOUNDRY_MODEL_DEPLOYMENT=${FOUNDRY_MODEL_DEPLOYMENT:+set}"
echo "AZURE_CONFIG_DIR=${AZURE_CONFIG_DIR:+set}"

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
test -n "${AZURE_CONFIG_DIR:-}" || {
  printf 'SMOKE_RESULT=FAIL %s\n' "missing runner Azure CLI profile" > /tmp/agent-framework-harness-smoke-result
  exit 1
}

az account show --output table || echo "(Azure CLI profile unavailable; the SDK call below is the auth gate)"
```

Use existence checks only. Do not compare subscription IDs, decode tokens,
inspect claims, print credentials, or validate GUID
shapes. Do not run `az login` or `azd`, regrant RBAC, deploy or provision
resources, install Azure CLI or system tools, hunt the filesystem for tools,
or start a server. The shared Foundry project and model are pre-provisioned
and read-only. Make one model call only.

## Step 1 — run the canonical harness once

Run from the repository root. Copilot Bash actions use fresh shells, so you
MUST execute this complete fenced block in one Bash tool call without
splitting it. The inherited `AZURE_CONFIG_DIR` points to the runner-owned
login; keep the model export and Python heredoc in the same Bash action.

```bash
set -euo pipefail
set +x

test -n "${AZURE_CONFIG_DIR:-}" || {
  printf 'SMOKE_RESULT=FAIL %s\n' "missing runner Azure CLI profile" > /tmp/agent-framework-harness-smoke-result
  exit 1
}

python3 -m venv /tmp/agent-framework-harness-venv
/tmp/agent-framework-harness-venv/bin/pip install --quiet \
  "agent-framework-core~=1.14.0" \
  "agent-framework-foundry~=1.11.0" \
  "agent-framework-foundry-hosting==1.0.0b260813" \
  "azure-ai-agentserver-core==2.1.0b1" \
  "azure-ai-agentserver-responses==2.1.0b1" \
  "azure-ai-agentserver-invocations==1.1.0b1" \
  "azure-identity~=1.25.3"

export AZURE_AI_MODEL_DEPLOYMENT_NAME="$FOUNDRY_MODEL_DEPLOYMENT"
echo "AZURE_AI_MODEL_DEPLOYMENT_NAME=${AZURE_AI_MODEL_DEPLOYMENT_NAME:+set}"

/tmp/agent-framework-harness-venv/bin/python - <<'PY'
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from agent_framework import Agent, AgentSession
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity.aio import AzureCliCredential

reference_dir = Path(
    "skills/agent-framework-harness/references/python"
).resolve()
sys.path.insert(0, str(reference_dir))

from hosted_harness import build_agent, build_server
from session_recovery import restore_session, serialize_session


async def main() -> None:
    print("HARNESS_REFERENCE_IMPORT_OK")
    async with AzureCliCredential(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        subscription=os.environ["AZURE_SUBSCRIPTION_ID"],
    ) as credential:
        agent = build_agent(credential=credential)
        assert isinstance(agent, Agent)
        assert agent.default_options["store"] is False
        print("HARNESS_AGENT_CONSTRUCTED")

        server = build_server(agent)
        assert isinstance(server, ResponsesHostServer)
        print("HOSTING_ADAPTER_CONSTRUCTED")

        session = restore_session(serialize_session(agent.create_session()))
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

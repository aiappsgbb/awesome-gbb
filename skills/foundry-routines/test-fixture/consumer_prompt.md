# Customer goal - `foundry-routines` skill smoke

You are a developer on a customer team. Prove that the `foundry-routines`
consumer contract works end-to-end against the CI Foundry project.

**This is an EXECUTION smoke, not a catalog inspection.** You MUST run every
Bash code block below in order. Execute each fenced Bash block as its own Bash
tool call. Do not combine multiple numbered steps into one command. Do NOT
create an ad-hoc combined smoke harness. Do NOT use shell process substitution.

Do NOT inspect repo files, do NOT run `validate-skills.py`, do NOT rebuild docs,
and do NOT run `git status`. This prompt is self-contained. Do NOT read, view,
grep, or glob `SKILL.md`, `upstream-pin.md`, workflow files, or unrelated
repository files. Do NOT create or modify tracked repository files. Do NOT
write a session plan. Do NOT create scratch scripts, wrappers, or planning
files. Do NOT edit any repository file. Do NOT edit the fixture or skill.
Execute Steps -1 through 8 directly.
If the live service rejects this documented contract, write the FAIL marker;
do not modify the repository to make the smoke pass.

Your only acceptable terminal state is a Bash tool call that writes the marker
file to `/tmp/foundry-routines-smoke-result`.

**CRITICAL - never invoke `copilot` recursively from a Bash tool.** You ARE the
running Copilot CLI process. Do NOT run `copilot -p ...`. Do NOT run `copilot --version`.
Do NOT install Copilot or invoke any other `copilot ...` command.
The workflow already captures your output through its outer `tee`; your job is
to execute the numbered Bash blocks directly.

---

## Step -1 - Acknowledge skill contract (mandatory FIRST action)

Your first action must be a separate Bash tool call containing only this
command. Do not combine it with Step 0 or any later work.

```bash
echo "Executing consumer smoke for skills/foundry-routines/SKILL.md"
```

---

## Environment available to your run

The workflow has pre-provisioned shared CI infrastructure. You consume it; do
not create or modify the project, model deployment, identities, or RBAC.

- `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` - populated by
  `azure/login@v2` OIDC upstream.
- `FOUNDRY_PROJECT_ENDPOINT` - the existing CI Foundry project endpoint.
- `FOUNDRY_MODEL_DEPLOYMENT` - the existing model deployment used by the
  temporary prompt agent.
- `az`, Python 3, and `pip` are already installed. Do not hunt for or install
  CLI tooling.

---

## Step 0 - Auth context (show, do not assert)

Print the auth context for the run log. Do not gate flow on the Azure CLI token
cache; Copilot CLI subprocesses do not always inherit it.

```bash
rm -f /tmp/foundry-routines-smoke-success
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
echo "FOUNDRY_MODEL_DEPLOYMENT=${FOUNDRY_MODEL_DEPLOYMENT:+set}"
az account show --output table || echo "(az cache not inherited - relying on SDK DefaultAzureCredential)"
```

If any required variable prints empty, stop the lifecycle and execute Step 8.
The absent success sentinel will produce the authoritative FAIL marker.

---

## Step 1 - Install the bounded SDK stack

Run this block verbatim:

```bash
set -euo pipefail
pip install --quiet "azure-ai-projects~=2.4.0" "azure-identity~=1.25.3" "httpx~=0.28.1"
python3 - <<'PY'
import azure.ai.projects as projects

parts = tuple(int(part) for part in projects.__version__.split(".")[:2])
assert parts == (2, 4), f"azure-ai-projects outside ~=2.4.0: {projects.__version__}"
print(f"azure-ai-projects=={projects.__version__}")
PY
```

---

## Step 2 - Initialize disposable names and state

The short UUID suffix prevents collisions between parallel matrix runs and
retries. State lives only under `/tmp`; never write state into the checkout.

```bash
set -euo pipefail
STATE_FILE="/tmp/foundry-routines-state.env"
SUCCESS_FILE="/tmp/foundry-routines-smoke-success"
EVIDENCE_FILE="/tmp/foundry-routines-smoke-evidence"
UUID=$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')
AGENT_REQUESTED_NAME="ci-smoke-routine-pa-${UUID}"
ROUTINE_NAME="ci-smoke-routine-${UUID}"
rm -f "$STATE_FILE" "$SUCCESS_FILE" "$EVIDENCE_FILE" /tmp/foundry-routines-smoke-result
: > "$EVIDENCE_FILE"
printf 'export STATE_FILE=%q\nexport SUCCESS_FILE=%q\nexport EVIDENCE_FILE=%q\nexport AGENT_REQUESTED_NAME=%q\nexport ROUTINE_NAME=%q\n' \
  "$STATE_FILE" "$SUCCESS_FILE" "$EVIDENCE_FILE" "$AGENT_REQUESTED_NAME" "$ROUTINE_NAME" \
  > "${STATE_FILE}.tmp"
mv "${STATE_FILE}.tmp" "$STATE_FILE"
echo "agent=${AGENT_REQUESTED_NAME} routine=${ROUTINE_NAME}"
```

---

## Step 3 - Create the temporary prompt agent

The routine service requires an agent with a configured agent identity.
`project.agents.create_version(...)` supplies that identity.

```bash
set -euo pipefail
source /tmp/foundry-routines-state.env
python3 - <<'PY'
import os
import shlex

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential

project = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
agent = project.agents.create_version(
    agent_name=os.environ["AGENT_REQUESTED_NAME"],
    definition=PromptAgentDefinition(
        model=os.environ["FOUNDRY_MODEL_DEPLOYMENT"],
        instructions="Echo back the input verbatim. Do not embellish.",
    ),
)
assert agent.name, "prompt agent returned empty name"
assert agent.version, "prompt agent returned empty version"
with open(os.environ["STATE_FILE"], "a", encoding="utf-8") as state:
    state.write(f"export AGENT_NAME={shlex.quote(str(agent.name))}\n")
    state.write(f"export AGENT_VERSION={shlex.quote(str(agent.version))}\n")
with open(os.environ["EVIDENCE_FILE"], "a", encoding="utf-8") as evidence:
    evidence.write("AGENT_CREATED\n")
print(f"prompt-agent-created: {agent.name} v{agent.version}")
PY
```

---

## Step 4 - Create the enabled monthly routine

Use the live-proven recurring schedule: midnight UTC on the first day of each
month. Keep the trigger and action shapes exact.

```bash
source /tmp/foundry-routines-state.env
python3 - <<'PY'
import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

client = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
routine = client.beta.routines.create_or_update(
    routine_name=os.environ["ROUTINE_NAME"],
    description="CI smoke for foundry-routines lifecycle.",
    enabled=True,
    triggers={
        "monthly-anchor": {
            "type": "schedule",
            "cron_expression": "0 0 1 * *",
            "time_zone": "UTC",
        }
    },
    action={
        "type": "invoke_agent_responses_api",
        "agent_name": os.environ["AGENT_NAME"],
    },
)
assert routine.name == os.environ["ROUTINE_NAME"], (
    f"routine name mismatch: {routine.name!r}"
)
assert routine.enabled is True, f"routine not enabled: {routine.enabled!r}"
with open(os.environ["EVIDENCE_FILE"], "a", encoding="utf-8") as evidence:
    evidence.write("ROUTINE_CREATED\n")
print(f"routine-created: {routine.name} enabled={routine.enabled}")
PY
```

---

## Step 5 - Dispatch the routine

The payload type must match the routine action type. A non-empty dispatch ID is
the hard asynchronous queueing contract; do not poll run history.

```bash
source /tmp/foundry-routines-state.env
python3 - <<'PY'
import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

client = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
result = client.beta.routines.dispatch(
    routine_name=os.environ["ROUTINE_NAME"],
    payload={
        "type": "invoke_agent_responses_api",
        "input": "Echo: live-routine-smoke",
    },
)
assert result.dispatch_id, "dispatch returned empty dispatch_id"
print(
    "routine-dispatched: "
    f"dispatch_id={result.dispatch_id} "
    f"task_id={result.task_id} "
    f"action_correlation_id={result.action_correlation_id}"
)
with open(os.environ["EVIDENCE_FILE"], "a", encoding="utf-8") as evidence:
    evidence.write("ROUTINE_DISPATCHED\n")
PY
```

---

## Step 6 - List and verify the routine

```bash
source /tmp/foundry-routines-state.env
python3 - <<'PY'
import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

client = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
names = [routine.name for routine in client.beta.routines.list()]
assert os.environ["ROUTINE_NAME"] in names, (
    f"routine not visible in list(): {names}"
)
with open(os.environ["EVIDENCE_FILE"], "a", encoding="utf-8") as evidence:
    evidence.write("ROUTINE_LISTED\n")
print(f"routine-list-ok: {len(names)} routines visible")
PY
```

---

## Step 7 - Delete the routine, clean the prompt agent, and seal success

Routine deletion is a hard PASS condition because the enabled recurring
routine is the direct output of this skill. Disable is best-effort because
delete removes the routine regardless. Prompt-agent cleanup is best-effort
per Pattern 25 and must never turn a proven routine lifecycle into FAIL.

```bash
set -euo pipefail
source /tmp/foundry-routines-state.env
python3 - <<'PY'
import os
import signal

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


def prompt_cleanup_timeout(_signum, _frame):
    raise TimeoutError("prompt-agent cleanup exceeded 120s")


project = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
routine_delete_error = None
try:
    project.beta.routines.disable(os.environ["ROUTINE_NAME"])
except Exception as exc:
    print(f"routine-disable-note: {type(exc).__name__} - {str(exc).splitlines()[0]}")

try:
    project.beta.routines.delete(os.environ["ROUTINE_NAME"])
    with open(os.environ["EVIDENCE_FILE"], "a", encoding="utf-8") as evidence:
        evidence.write("ROUTINE_DELETED\n")
    print(f"routine-cleanup-ok: {os.environ['ROUTINE_NAME']}")
except Exception as exc:
    routine_delete_error = exc
    print(f"routine-delete-fail: {type(exc).__name__} - {str(exc).splitlines()[0]}")

previous_alarm_handler = signal.signal(signal.SIGALRM, prompt_cleanup_timeout)
signal.alarm(120)
try:
    try:
        project.agents.delete_version(
            os.environ["AGENT_NAME"],
            os.environ["AGENT_VERSION"],
        )
        print(
            "prompt-agent-cleanup-ok: "
            f"{os.environ['AGENT_NAME']} v{os.environ['AGENT_VERSION']}"
        )
    except Exception as exc:
        print(
            "prompt-agent-cleanup-note: "
            f"{type(exc).__name__} - {str(exc).splitlines()[0]}"
        )
finally:
    signal.alarm(0)
    signal.signal(signal.SIGALRM, previous_alarm_handler)

if routine_delete_error is not None:
    raise routine_delete_error
PY
EXPECTED_EVIDENCE=$(printf '%s\n' \
  AGENT_CREATED \
  ROUTINE_CREATED \
  ROUTINE_DISPATCHED \
  ROUTINE_LISTED \
  ROUTINE_DELETED)
ACTUAL_EVIDENCE=$(cat "$EVIDENCE_FILE")
if [[ "$ACTUAL_EVIDENCE" == "$EXPECTED_EVIDENCE" ]]; then
  : > "$SUCCESS_FILE"
else
  echo "ordered lifecycle evidence mismatch"
  exit 1
fi
```

---

## Step 8 - Write the result marker (deterministic, MANDATORY)

Your FINAL action is to invoke the Bash tool with this block exactly.
The file's literal byte content is what CI grades; your assistant-text reply is
NOT graded. Do not replace this block with `echo PASS`, `printf PASS`, prose,
or an ad-hoc marker command.

```bash
if [[ -f /tmp/foundry-routines-smoke-success ]]; then
  printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-routines-smoke-result
else
  printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-routines-smoke-result
  exit 1
fi
```

The marker file is the single source of truth. Do not print the marker token
elsewhere. The success form is exactly the 18 bytes `SMOKE_RESULT=PASS\n`;
anything else is graded FAIL by `cmp -s`.

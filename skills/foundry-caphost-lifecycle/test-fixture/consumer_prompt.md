# Customer goal — `foundry-caphost-lifecycle` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-caphost-lifecycle`
skill works end-to-end against your CI Azure subscription.

**This is an EXECUTION smoke, not a catalog inspection.** You MUST run every
Bash code block below in order. Step 10 is the single evidence gate that writes
exactly one PASS/FAIL marker. Do NOT inspect repo files, do NOT
run `validate-skills.py`, do NOT rebuild docs, and do NOT run `git status` —
those are catalog-author concerns, not consumer-smoke concerns. Your only
acceptable terminal state is a Bash tool call that writes the marker file to
`/tmp/foundry-caphost-lifecycle-smoke-result`.

This prompt is self-contained. Do NOT read, view, grep, or glob `SKILL.md`,
`upstream-pin.md`, the workflow, or unrelated repository files. Do NOT create
or modify tracked repository files. Execute the numbered lifecycle steps
directly using the commands and code in this prompt.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You ARE the
running Copilot CLI process. Do NOT run `copilot -p ...`, `copilot --version`,
`npm install -g @github/copilot`, or any other `copilot ...` invocation from
inside a Bash tool call. The workflow already captures your output through its
outer `tee`; your job is to execute Steps -1 through 10 directly.

---

## Step -1 — Acknowledge the skill contract (mandatory FIRST action)

Your first action must be a separate Bash tool call containing only this
command. Do not combine it with Step 0 or any later work.

```bash
echo "Executing consumer smoke for skills/foundry-caphost-lifecycle/SKILL.md"
```

---

## Environment available to your run

The workflow has pre-provisioned shared CI infrastructure. You consume it;
you do NOT create it. The account lifecycle runs in the dedicated unlocked disposable CI resource group so every run can delete and purge its own account.

- `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` —
  populated by `azure/login@v2` OIDC upstream.
- Resource group: `rg-awesome-gbb-caphost-ci` (Sweden Central).
  Pre-provisioned specifically for this destructive lifecycle smoke.
  Do NOT run `az group create`.

**Pre-granted RBAC (do NOT re-grant — propagation is 5-15 min and would
race the workflow timeout):**

- The UAMI `uami-awesome-gbb-ci` holds **Contributor** on
  `rg-awesome-gbb-caphost-ci`. That is sufficient for creating + deleting a
  Cognitive Services account and CRUDing capability hosts on it. Per
  MS Learn the role required for capability host create is `Contributor`
  on the Foundry account — and `Contributor` on the parent RG covers it.
- If a caphost PUT or `az cognitiveservices account purge` returns 401 or
  403, **STOP** and write the FAIL marker with reason `RBAC chain
  insufficient: <call-name> returned <status>`. Do NOT try to grant a
  fresh role yourself — that races propagation against the workflow
  timeout (Pattern 7 in AGENTS.md § 9.7).

**Tooling pre-installed by the workflow** (Pattern 15 — AGENTS.md § 9.7):

- `az` CLI, Python 3, and `pip` are pre-installed by the GHA runner.
- The Python SDK packages this fixture needs (`azure-mgmt-cognitiveservices`,
  `azure-identity`) will be `pip install`'d inside Step 1 with the cap
  windows declared in the skill's pin file.

---

## Step 0 — Auth context (show, do not assert)

Print the auth context for the run log. Do NOT gate flow on `az account
show` — `azure/login@v2` already validated the credentials upstream
(Pattern 17 — show-don't-assert):

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
az account show --output table || echo "(az cache not inherited — relying on SDK DefaultAzureCredential)"
```

If any of `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`
prints empty, the workflow's `env:` block is broken (AGENTS.md § 9.7
Pattern 11). That is a workflow bug, not a skill bug. Write the FAIL
marker (Step 10) with reason `auth context missing: <var-name>` and stop.

---

## Step 1 — Resource naming + SDK install

All Azure resources you create MUST carry a short-UUID suffix
(Pattern 3 / Pattern 15.3) so parallel matrix runs and retries don't
collide on the same name. Capture the suffix once and reuse:

```bash
STATE_FILE="/tmp/foundry-caphost-lifecycle-state.env"
EVIDENCE_FILE="/tmp/foundry-caphost-lifecycle-smoke-evidence"
UUID=$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')
ACCT="caphost-smoke-${UUID}"
RG="rg-awesome-gbb-caphost-ci"
LOC="swedencentral"
echo "ACCT=$ACCT  RG=$RG  LOC=$LOC"
: > "$EVIDENCE_FILE"
printf 'export ACCT=%q\nexport RG=%q\nexport LOC=%q\nexport EVIDENCE_FILE=%q\n' \
  "$ACCT" "$RG" "$LOC" "$EVIDENCE_FILE" > "${STATE_FILE}.tmp"
mv "${STATE_FILE}.tmp" "$STATE_FILE"
```

Install the Python SDK packages the skill uses (the cap windows match
`skills/foundry-caphost-lifecycle/references/upstream-pin.md`):

```bash
pip install --quiet --upgrade \
  "azure-mgmt-cognitiveservices~=14.1.0" \
  "azure-identity~=1.25.3"
```

---

## Step 2 — Create the parent Cognitive Services account (`AIServices`/`S0`)

Capability hosts attach to a `Microsoft.CognitiveServices/accounts` resource
with `kind=AIServices`. Create the lightest possible account — no model
deployments, no VNet injection, no private endpoints — because this
fixture is testing the **caphost lifecycle**, not greenfield Foundry
deploy (which is owned by `foundry-vnet-deploy`):

```bash
source /tmp/foundry-caphost-lifecycle-state.env
az cognitiveservices account create \
  -n "$ACCT" \
  -g "$RG" \
  -l "$LOC" \
  --kind AIServices \
  --sku S0 \
  --custom-domain "$ACCT" \
  --yes
```

Then poll `provisioningState` until `Succeeded` (typical: 30s-2min;
budget 5min):

```bash
source /tmp/foundry-caphost-lifecycle-state.env
for i in $(seq 1 60); do
  STATE=$(az cognitiveservices account show -n "$ACCT" -g "$RG" \
            --query "properties.provisioningState" -o tsv 2>/dev/null || echo "Pending")
  echo "account provisioningState[$i] = $STATE"
  [[ "$STATE" == "Succeeded" ]] && break
  sleep 5
done
[[ "$STATE" == "Succeeded" ]] || {
  echo "account never reached Succeeded (last: $STATE)"
  # FAIL handler in Step 10 will catch this via the marker write
  exit 1
}
printf 'ACCOUNT_CREATED\n' >> "$EVIDENCE_FILE"
```

If account create returns 401 / 403 → write FAIL marker per Step 10 with
reason `account create returned <status>` and stop.

---

## Step 3 — PUT account capability host (Agents kind)

Per `SKILL.md` § 6.1 the account capability host PUT body for an
agent-enabled account (with no BYO connections, no `customerSubnet`) is
the minimal shape. Use the `azure-mgmt-cognitiveservices` SDK — the skill
documents this as the runnable path because there is no `az
cognitiveservices account capability-host` command group as of api-version
2025-06-01 (SKILL.md § 11 anti-pattern).

Wrap the PUT call in the skill's **Pattern 23 concurrent-op retry loop**
(SKILL.md § 6.3): max 6 attempts, 30s backoff, retry ONLY on 409
`currently in non creating`. On any other failure, FAIL immediately.

```bash
source /tmp/foundry-caphost-lifecycle-state.env
python3 - <<'PY'
import os, sys, time
from azure.identity import DefaultAzureCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.mgmt.cognitiveservices.models import CapabilityHost
from azure.core.exceptions import HttpResponseError

SUB = os.environ["AZURE_SUBSCRIPTION_ID"]
RG  = os.environ["RG"]
ACCT = os.environ["ACCT"]
NAME = "default"

client = CognitiveServicesManagementClient(DefaultAzureCredential(), SUB)
body = CapabilityHost(properties={"capabilityHostKind": "Agents"})

for attempt in range(6):
    try:
        poller = client.capability_hosts.begin_create_or_update(
            resource_group_name=RG, account_name=ACCT,
            capability_host_name=NAME, capability_host=body,
        )
        result = poller.result()
        state = result.properties.provisioning_state
        if state != "Succeeded":
            print(f"caphost_put_FAIL unexpected_state={state}")
            sys.exit(2)
        with open(os.environ["EVIDENCE_FILE"], "a", encoding="utf-8") as evidence:
            evidence.write("CAPHOST_CREATED\n")
        print(f"caphost_put_state={state}")
        sys.exit(0)
    except HttpResponseError as e:
        msg = (e.message or "").lower()
        if "currently in non creating" in msg and attempt < 5:
            print(f"caphost_put_retry attempt={attempt} (concurrent op)")
            time.sleep(30)
            continue
        print(f"caphost_put_FAIL status={e.status_code} msg={e.message}")
        sys.exit(2)
sys.exit(3)  # ran out of retries
PY
```

Expected stdout (last line): `caphost_put_state=Succeeded`. Any other
final line is hard FAIL — write the marker per Step 10.

---

## Step 4 — GET the caphost and assert healthy

```bash
source /tmp/foundry-caphost-lifecycle-state.env
SHAPE_OK=$(az rest --method get \
  --url "https://management.azure.com/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${RG}/providers/Microsoft.CognitiveServices/accounts/${ACCT}/capabilityHosts/default?api-version=2025-06-01" \
  --query "name == 'default' && properties.provisioningState == 'Succeeded' && properties.capabilityHostKind == 'Agents'" \
  -o tsv)
[[ "$SHAPE_OK" == "true" ]] || exit 1
printf 'CAPHOST_GET_OK\n' >> "$EVIDENCE_FILE"
```

The Bash assertion makes any wrong state, kind, or name a hard failure.

---

## Step 5 — Idempotent replay: PUT same name + same body → 200 OK

Per MS Learn (and SKILL.md § 4 Constraints recap), the same-name + same-
config PUT MUST return the existing resource (200) without re-creating
anything. Run the same SDK call from Step 3 a second time:

```bash
source /tmp/foundry-caphost-lifecycle-state.env
python3 - <<'PY'
import json, os, sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from azure.identity import DefaultAzureCredential

SUB = os.environ["AZURE_SUBSCRIPTION_ID"]
RG = os.environ["RG"]
ACCT = os.environ["ACCT"]
url = (
    f"https://management.azure.com/subscriptions/{SUB}/resourceGroups/{RG}"
    f"/providers/Microsoft.CognitiveServices/accounts/{ACCT}"
    "/capabilityHosts/default?api-version=2025-06-01"
)
token = DefaultAzureCredential().get_token(
    "https://management.azure.com/.default"
).token
request = Request(
    url,
    method="PUT",
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    },
    data=json.dumps(
        {"properties": {"capabilityHostKind": "Agents"}}
    ).encode("utf-8"),
)
try:
    with urlopen(request, timeout=120) as response:
        status = response.status
        payload = json.load(response)
except HTTPError as exc:
    print(f"caphost_replay_FAIL status={exc.code}")
    sys.exit(2)
if status != 200:
    print(f"caphost_replay_FAIL status={status}")
    sys.exit(2)
if payload.get("properties", {}).get("provisioningState") != "Succeeded":
    print("caphost_replay_FAIL unexpected_state")
    sys.exit(2)
with open(os.environ["EVIDENCE_FILE"], "a", encoding="utf-8") as evidence:
    evidence.write("CAPHOST_REPLAY_200\n")
print("caphost_replay_status=200")
PY
```

Expected: `caphost_replay_status=200`. The code hard-fails any other HTTP
status or response state.

---

## Step 6 — DELETE the caphost

Per SKILL.md § 7.2, DELETE caphost is a separate REST verb that removes
the caphost without deleting the parent account. Wrap in the same
Pattern 23 retry on `currently in non creating` 409.

```bash
source /tmp/foundry-caphost-lifecycle-state.env
python3 - <<'PY'
import os, sys, time
from azure.identity import DefaultAzureCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

SUB = os.environ["AZURE_SUBSCRIPTION_ID"]
RG  = os.environ["RG"]
ACCT = os.environ["ACCT"]
NAME = "default"

client = CognitiveServicesManagementClient(DefaultAzureCredential(), SUB)

for attempt in range(6):
    try:
        client.capability_hosts.begin_delete(
            resource_group_name=RG, account_name=ACCT,
            capability_host_name=NAME,
        ).result()
        print("caphost_delete_ok")
        break
    except ResourceNotFoundError:
        print("caphost_delete_already_gone")
        print("caphost_absent_after_delete")
        with open(os.environ["EVIDENCE_FILE"], "a", encoding="utf-8") as evidence:
            evidence.write("CAPHOST_DELETED\n")
        sys.exit(0)
    except HttpResponseError as e:
        msg = (e.message or "").lower()
        if "currently in non creating" in msg and attempt < 5:
            print(f"caphost_delete_retry attempt={attempt}")
            time.sleep(30)
            continue
        print(f"caphost_delete_FAIL status={e.status_code} msg={e.message}")
        sys.exit(2)
else:
    sys.exit(3)

for attempt in range(12):
    try:
        client.capability_hosts.get(
          resource_group_name=RG,
          account_name=ACCT,
          capability_host_name=NAME,
        )
    except ResourceNotFoundError:
        print("caphost_absent_after_delete")
        with open(os.environ["EVIDENCE_FILE"], "a", encoding="utf-8") as evidence:
            evidence.write("CAPHOST_DELETED\n")
        sys.exit(0)
    time.sleep(5)
print("caphost_delete_FAIL resource_still_exists")
sys.exit(2)
PY
```

Expected: both `caphost_delete_ok` (or `caphost_delete_already_gone`) and
`caphost_absent_after_delete`. Failure to observe absence within 60 seconds
is a hard failure.

Steps 1-9 are the **hard PASS contract** for this full lifecycle fixture.

---

## Step 7 — Soft-delete the parent account

```bash
source /tmp/foundry-caphost-lifecycle-state.env
az cognitiveservices account delete -n "$ACCT" -g "$RG"
```

This should exit 0. If it doesn't, write the hard FAIL marker. Account
deletion is part of this skill's core contract.

---

## Step 8 — `list-deleted` should show the account is in the soft-delete index

There can be a brief consistency lag (5-60s) between the delete return
and the soft-delete index reflecting it. Poll up to 90 seconds:

```bash
source /tmp/foundry-caphost-lifecycle-state.env
for i in $(seq 1 18); do
  if ! FOUND=$(az cognitiveservices account list-deleted \
      --query "[?name=='${ACCT}'].name | [0]" -o tsv 2>/dev/null); then
    exit 1
  fi
  echo "list-deleted attempt[$i] = '${FOUND}'"
  [[ "$FOUND" == "$ACCT" ]] && break
  sleep 5
done
[[ "$FOUND" == "$ACCT" ]] || exit 1
printf 'ACCOUNT_SOFT_DELETED\n' >> "$EVIDENCE_FILE"
```

Expected: Account entered the soft-delete index.

---

## Step 9 — Purge the account, then verify it's gone from `list-deleted`

```bash
source /tmp/foundry-caphost-lifecycle-state.env
az cognitiveservices account purge -l "$LOC" -n "$ACCT" -g "$RG"
```

Per SKILL.md § 8.5 the purge itself takes 1-3 min typical / up to 10 min
p99. Then the soft-delete index updates within seconds:

```bash
source /tmp/foundry-caphost-lifecycle-state.env
for i in $(seq 1 18); do
  if ! STILL=$(az cognitiveservices account list-deleted \
      --query "[?name=='${ACCT}'].name | [0]" -o tsv 2>/dev/null); then
    exit 1
  fi
  echo "post-purge list-deleted attempt[$i] = '${STILL}'"
  [[ -z "$STILL" ]] && break
  sleep 10
done
[[ -z "$STILL" ]] || exit 1
printf 'ACCOUNT_PURGED\n' >> "$EVIDENCE_FILE"
```

Expected: Account purge succeeded and the account left the soft-delete index.

---

## Step 10 — Marker contract (deterministic, MANDATORY)

Your FINAL action is to invoke the Bash tool to write the marker file.
The file's literal byte content is what CI grades; your assistant-text
reply is NOT graded.

**HARD PASS conditions (Steps 1-9 all succeeded):**

- Account created and reached `provisioningState=Succeeded`
- Account caphost PUT returned `Succeeded` (Step 3)
- Caphost GET returned `Succeeded` + `kind=Agents` + `name=default` (Step 4)
- Idempotent replay PUT returned HTTP 200 + `Succeeded` (Step 5)
- Caphost DELETE returned ok (or `already_gone`) and post-delete GET was 404 (Step 6)
- Account entered the soft-delete index (Steps 7-8)
- Account purge succeeded and the account left the soft-delete index (Step 9)

The final block compares the exact ordered evidence sequence before writing
the authoritative marker:

```bash
source /tmp/foundry-caphost-lifecycle-state.env
cleanup_failed_account() {
  local active=""
  local active_after=""
  local found=""
  if ! active=$(az cognitiveservices account list -g "$RG" \
      --query "[?name=='${ACCT}'].name | [0]" -o tsv 2>/dev/null); then
    return 1
  fi
  if [[ "$active" == "$ACCT" ]]; then
    az cognitiveservices account delete -n "$ACCT" -g "$RG" || return 1
  fi
  for _ in $(seq 1 18); do
    if ! found=$(az cognitiveservices account list-deleted \
        --query "[?name=='${ACCT}'].name | [0]" -o tsv 2>/dev/null); then
      return 1
    fi
    [[ "$found" == "$ACCT" ]] && break
    if [[ "$active" != "$ACCT" ]] &&
        ! grep -qx 'ACCOUNT_CREATED' "$EVIDENCE_FILE"; then
      return 0
    fi
    sleep 5
  done
  if [[ "$found" != "$ACCT" ]]; then
    if ! active_after=$(az cognitiveservices account list -g "$RG" \
        --query "[?name=='${ACCT}'].name | [0]" -o tsv 2>/dev/null); then
      return 1
    fi
    [[ -z "$active_after" ]] && return 0
    return 1
  fi
  az cognitiveservices account purge -l "$LOC" -n "$ACCT" -g "$RG"
}
EXPECTED_EVIDENCE=$(printf '%s\n' \
  ACCOUNT_CREATED \
  CAPHOST_CREATED \
  CAPHOST_GET_OK \
  CAPHOST_REPLAY_200 \
  CAPHOST_DELETED \
  ACCOUNT_SOFT_DELETED \
  ACCOUNT_PURGED)
ACTUAL_EVIDENCE=$(cat "$EVIDENCE_FILE")
if [[ "$ACTUAL_EVIDENCE" == "$EXPECTED_EVIDENCE" ]]; then
  printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-caphost-lifecycle-smoke-result
else
  if ! cleanup_failed_account; then
    echo "NOTE: failure cleanup incomplete for ${ACCT}"
  fi
  printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-caphost-lifecycle-smoke-result
  exit 1
fi
```

**HARD FAIL conditions** (any of):

- Step 0 detected missing `AZURE_*` env vars
- Step 2 account create returned non-zero or never reached `Succeeded`
- Step 3 caphost PUT returned anything other than `Succeeded` after the
  retry loop completed
- Step 4 caphost GET returned a non-`Succeeded` state or wrong shape
- Step 5 idempotent replay was rejected (any 400, any non-200/`Succeeded`)
- Step 6 caphost DELETE returned a non-retryable error
- Step 8 did not observe the account in the soft-delete index
- Step 9 purge failed or the account remained in the soft-delete index
- Caphost PUT or DELETE returned 401 / 403 / `AuthorizationFailed`
  (per § "Pre-granted RBAC" above this is `RBAC chain insufficient`)

The marker file is single-source-of-truth. Do **NOT** print the marker
token anywhere else in your reply — no echoes, no summaries, no fenced
code blocks containing the literal `SMOKE_RESULT=PASS` or
`SMOKE_RESULT=FAIL` string. The Bash tool write is the only legitimate
emission path (Pattern 12, AGENTS.md § 9.7).

The marker line is exactly the 18 bytes `SMOKE_RESULT=PASS\n` or the FAIL
form; anything else is graded FAIL by `cmp -s`.

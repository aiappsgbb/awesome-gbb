# Customer goal — `foundry-caphost-lifecycle` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-caphost-lifecycle`
skill works end-to-end against your CI Azure subscription.

Do whatever the skill tells you to do. Do NOT improvise from training-data
knowledge of the Cognitive Services REST API or the `az` CLI — read the
skill's `SKILL.md` (under `skills/foundry-caphost-lifecycle/`) first, and
follow its documented contract. If your memory of how capability host CRUD,
soft-delete, or purge should look conflicts with what the skill says, **the
skill wins**.

---

## Environment available to your run

The workflow has pre-provisioned shared CI infrastructure. You consume it;
you do NOT create it.

- `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` —
  populated by `azure/login@v2` OIDC upstream.
- Resource group: `rg-awesome-gbb-ci` (Sweden Central). Pre-provisioned.
  Do NOT run `az group create`.

**Pre-granted RBAC (do NOT re-grant — propagation is 5-15 min and would
race the workflow timeout):**

- The UAMI `uami-awesome-gbb-ci` holds **Contributor** on
  `rg-awesome-gbb-ci`. That is sufficient for creating + deleting a
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
UUID=$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')
ACCT="caphost-smoke-${UUID}"
RG="rg-awesome-gbb-ci"
LOC="swedencentral"
echo "ACCT=$ACCT  RG=$RG  LOC=$LOC"
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

```python
# caphost_put.py
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
        print(f"caphost_put_state={result.properties.provisioning_state}")
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
```

Run it:

```bash
RG="$RG" ACCT="$ACCT" python3 caphost_put.py
```

Expected stdout (last line): `caphost_put_state=Succeeded`. Any other
final line is hard FAIL — write the marker per Step 10.

---

## Step 4 — GET the caphost and assert healthy

```bash
az rest --method get \
  --url "https://management.azure.com/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${RG}/providers/Microsoft.CognitiveServices/accounts/${ACCT}/capabilityHosts/default?api-version=2025-06-01" \
  --query "{name:name, state:properties.provisioningState, kind:properties.capabilityHostKind}" \
  -o json
```

Assert: `state == "Succeeded"`, `kind == "Agents"`, `name == "default"`.
Anything else → FAIL with reason `caphost GET returned unexpected shape`.

---

## Step 5 — Idempotent replay: PUT same name + same body → 200 OK

Per MS Learn (and SKILL.md § 4 Constraints recap), the same-name + same-
config PUT MUST return the existing resource (200) without re-creating
anything. Run the same SDK call from Step 3 a second time:

```bash
RG="$RG" ACCT="$ACCT" python3 caphost_put.py
```

Expected: again `caphost_put_state=Succeeded` — no `caphost_put_FAIL`
line, no `caphost_put_retry` line on the first attempt. This is the
idempotency contract.

---

## Step 6 — DELETE the caphost

Per SKILL.md § 7.2, DELETE caphost is a separate REST verb that removes
the caphost without deleting the parent account. Wrap in the same
Pattern 23 retry on `currently in non creating` 409.

```python
# caphost_delete.py
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
        sys.exit(0)
    except ResourceNotFoundError:
        print("caphost_delete_already_gone")
        sys.exit(0)
    except HttpResponseError as e:
        msg = (e.message or "").lower()
        if "currently in non creating" in msg and attempt < 5:
            print(f"caphost_delete_retry attempt={attempt}")
            time.sleep(30)
            continue
        print(f"caphost_delete_FAIL status={e.status_code} msg={e.message}")
        sys.exit(2)
sys.exit(3)
```

```bash
RG="$RG" ACCT="$ACCT" python3 caphost_delete.py
```

Expected: `caphost_delete_ok`. Then verify with a GET — expect 404:

```bash
HTTP=$(az rest --method get \
  --url "https://management.azure.com/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${RG}/providers/Microsoft.CognitiveServices/accounts/${ACCT}/capabilityHosts/default?api-version=2025-06-01" \
  -o tsv 2>&1 | head -1) || true
echo "caphost GET after delete: $HTTP"
# The 404 may show up as "ResourceNotFound" in the az error text — either is fine.
```

Steps 1-6 are the **hard PASS contract** for this fixture. Steps 7-9
below exercise the account teardown surface; per AGENTS.md § 9.7
Pattern 25 they are best-effort soft-PASS (the `rg-awesome-gbb-ci`
janitor sweeps `caphost-smoke-*` weekly if cleanup fails).

---

## Step 7 — Soft-delete the parent account

```bash
az cognitiveservices account delete -n "$ACCT" -g "$RG"
```

This should exit 0. If it doesn't, the FAIL goes into the soft-PASS
NOTE for cleanup (Pattern 25), not the hard FAIL marker.

---

## Step 8 — `list-deleted` should show the account is in the soft-delete index

There can be a brief consistency lag (5-60s) between the delete return
and the soft-delete index reflecting it. Poll up to 90 seconds:

```bash
for i in $(seq 1 18); do
  FOUND=$(az cognitiveservices account list-deleted -l "$LOC" \
            --query "[?name=='${ACCT}'].name" -o tsv 2>/dev/null || echo "")
  echo "list-deleted attempt[$i] = '${FOUND}'"
  [[ "$FOUND" == "$ACCT" ]] && break
  sleep 5
done
[[ "$FOUND" == "$ACCT" ]] || echo "NOTE: account not in soft-deleted index after 90s (Pattern 25 soft-PASS)"
```

---

## Step 9 — Purge the account, then verify it's gone from `list-deleted`

```bash
az cognitiveservices account purge -l "$LOC" -n "$ACCT" -g "$RG"
```

Per SKILL.md § 8.5 the purge itself takes 1-3 min typical / up to 10 min
p99. Then the soft-delete index updates within seconds:

```bash
for i in $(seq 1 18); do
  STILL=$(az cognitiveservices account list-deleted -l "$LOC" \
            --query "[?name=='${ACCT}'].name" -o tsv 2>/dev/null || echo "")
  echo "post-purge list-deleted attempt[$i] = '${STILL}'"
  [[ -z "$STILL" ]] && break
  sleep 10
done
[[ -z "$STILL" ]] || echo "NOTE: account still in soft-deleted index 3min after purge (Pattern 25 soft-PASS)"
```

---

## Step 10 — Marker contract (deterministic, MANDATORY)

Your FINAL action is to invoke the Bash tool to write the marker file.
The file's literal byte content is what CI grades; your assistant-text
reply is NOT graded.

**HARD PASS conditions (Steps 1-6 all succeeded):**

- Account created and reached `provisioningState=Succeeded`
- Account caphost PUT returned `Succeeded` (Step 3)
- Caphost GET returned `Succeeded` + `kind=Agents` + `name=default` (Step 4)
- Idempotent replay PUT returned `Succeeded` (Step 5)
- Caphost DELETE returned ok (or `already_gone`) and post-delete GET was 404 (Step 6)

If all of the above hold, write PASS:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-caphost-lifecycle-smoke-result
```

This is true **even if Steps 7-9 (account teardown) had problems** — those
are Pattern 25 best-effort hygiene; the cleanup NOTEs above already
captured the orphan for the janitor to sweep.

**HARD FAIL conditions** (any of):

- Step 0 detected missing `AZURE_*` env vars
- Step 2 account create returned non-zero or never reached `Succeeded`
- Step 3 caphost PUT returned anything other than `Succeeded` after the
  retry loop completed
- Step 4 caphost GET returned a non-`Succeeded` state or wrong shape
- Step 5 idempotent replay was rejected (any 400, any non-200/`Succeeded`)
- Step 6 caphost DELETE returned a non-retryable error
- Caphost PUT or DELETE returned 401 / 403 / `AuthorizationFailed`
  (per § "Pre-granted RBAC" above this is `RBAC chain insufficient`)

On hard FAIL:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-caphost-lifecycle-smoke-result
```

The marker file is single-source-of-truth. Do **NOT** print the marker
token anywhere else in your reply — no echoes, no summaries, no fenced
code blocks containing the literal `SMOKE_RESULT=PASS` or
`SMOKE_RESULT=FAIL` string. The Bash tool write is the only legitimate
emission path (Pattern 12, AGENTS.md § 9.7).

Pattern 25 soft-PASS NOTEs from Steps 7-9 (orphan-resource
`caphost-smoke-${UUID}` left in `rg-awesome-gbb-ci` for the janitor)
belong in the transcript only — NEVER in the marker file. The marker
line is exactly the 18 bytes `SMOKE_RESULT=PASS\n` or the FAIL form;
anything else is graded FAIL by `cmp -s`.

---
name: foundry-caphost-lifecycle
description: >
  Day-2 lifecycle of Microsoft Foundry capability hosts — the operational layer
  on top of MS Learn's create-only guidance. Covers idempotent create
  (REST 2025-06-01), inspect/GET, delete, **soft-delete + purge of the parent
  Cognitive Services account** (the only op that releases the
  `serviceAssociationLink` on the agent subnet), redeploy guard for
  `Subnet already in use`, concurrent-op retry, idempotency rules, and
  soft-delete recovery (48h window).
  USE FOR: capability host lifecycle, caphost delete, caphost purge,
  soft-delete recover, serviceAssociationLink release, Subnet already in use,
  caphost idempotency, caphost 409 concurrent op, redeploy after teardown,
  az cognitiveservices account purge.
  DO NOT USE FOR: greenfield BYO-VNet Foundry deploy (use foundry-vnet-deploy),
  azd-template Foundry deploy (use threadlight-deploy or foundry-hosted-agents),
  spoke onboarding (use citadel-spoke-onboarding), tenant isolation
  (use azure-tenant-isolation).
metadata:
  version: "1.0.1"
---

# Foundry Capability Host Lifecycle — Day-2 Operations

## 1. Goal

This skill teaches **Day-2 operations** for Microsoft Foundry capability hosts: how to
**inspect**, **idempotently re-create**, **delete**, **soft-delete the parent account**,
**purge**, and **redeploy** without tripping the `Subnet already in use` failure that
blocks every team that has ever torn down a VNet-injected Foundry account.

This is **explicitly not greenfield create** — for first-time BYO-VNet deploys see
[`foundry-vnet-deploy`](../foundry-vnet-deploy/SKILL.md), and for the azd template
flow see [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) or
[`threadlight-deploy`](https://github.com/aiappsgbb/threadlight-skills/blob/main/skills/threadlight-deploy/SKILL.md).
This skill is the field-experience overlay on top of the MS Learn capability-hosts
page ([learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts))
that ships with the operational knowledge MS Learn does not document.

## 2. When to use

Trigger this skill whenever any of these are true:

- You teardown'd a Foundry VNet-injected account and now `az deployment group create`
  fails with `Subnet already in use` (or `SubnetIsFull` referencing a
  `serviceAssociationLink`) when you try to redeploy into the **same** agent subnet.
- A caphost create is stuck in `Creating` for more than 10 minutes (the upstream
  operation has a documented ~5-15 min p99; longer means hung — go to § 9).
- You need to **change the connections** referenced by a project capability host
  (e.g., swap a Cosmos connection). MS Learn is explicit: updates are not supported;
  delete + recreate is the only path.
- You need to fully reclaim the soft-deleted account name within the 48h window
  (so a new account can be created with the **same** custom domain).
- You want a clean teardown that releases the `serviceAssociationLink` on the agent
  subnet AND removes the hidden ACA Managed Environment that the capability host
  provisioned under the covers.
- You have a soft-deleted account that needs to be **recovered** (not purged)
  before the 48h window expires.

If none of those describe your situation and you're doing first-time create, stop
and use [`foundry-vnet-deploy`](../foundry-vnet-deploy/SKILL.md) instead.

## 3. What MS Learn covers vs what this skill adds

MS Learn ([capability-hosts](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts))
is the authoritative source for the REST API surface and create-time semantics.
Use it for the contract. This skill exists because MS Learn does **not** cover the
operational reality of Day-2.

| Concern | MS Learn | This skill |
|---|---|---|
| Account + project caphost REST shape (PUT/GET) | ✅ | references it |
| Idempotency rules (200/400/409 matrix) | ✅ | retry pattern (§ 6) |
| `One caphost per scope` constraint | ✅ | redeploy implications (§ 9) |
| `Updates not supported — delete and recreate` | ✅ | safe-replace flow (§ 7) |
| Account caphost prerequisite for project caphost | ✅ | inspect order (§ 5) |
| DELETE caphost REST endpoint | ✅ | what it does/doesn't free (§ 7) |
| **Deleting caphost releases the SAL on the agent subnet** | ❌ | **FALSE** — only purging the parent account does (§ 8, § 9) |
| **`az cognitiveservices account purge` semantics** | ❌ | full sequence (§ 8) |
| **48h soft-delete window + recovery** | ❌ | when to recover vs purge (§ 10) |
| **Hidden Managed ACA Environment created by caphost** | ❌ | only released on account purge (§ 8) |
| **Redeploy-after-teardown failure mode** | ❌ | the `Subnet already in use` guard (§ 9) |
| Concurrent-op 409 retry (`currently in non creating`) | ✅ pseudocode | runnable retry loop (§ 6) |

> **The single most important field-verified rule:** **deleting a capability host
> does NOT release the `serviceAssociationLink` on the agent subnet.** Only purging
> the parent `Microsoft.CognitiveServices/accounts` resource releases it. If you
> need to redeploy into the same subnet, you MUST purge — soft-delete alone is not
> enough. See § 8 and § 9 for the exact sequence and the symptom-to-fix mapping.

## 4. Constraints recap (from MS Learn)

Read these once. They drive every Day-2 decision below.

| Constraint | Rule | Source |
|---|---|---|
| **One caphost per scope** | Each account, each project: only one active capability host. Second host with different name → 409 Conflict. | [MS Learn § Constraints](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts) |
| **No updates** | There is no PATCH support. Configuration changes require DELETE + recreate. | [MS Learn § Constraints](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts) |
| **Account caphost prerequisite** | You cannot create a project capability host unless an account-level one already exists. | [MS Learn § Constraints](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts) |
| **Idempotency: same-name + same-config** | Returns 200 OK with the existing resource. Safe to retry. | [MS Learn § Idempotent behavior](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts) |
| **Idempotency: same-name + different config** | Returns 400 Bad Request. No silent in-place modification. | [MS Learn § Idempotent behavior](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts) |
| **Idempotency: different name at occupied scope** | Returns 409 Conflict (one-per-scope). | [MS Learn § Idempotent behavior](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts) |
| **Concurrent operation in flight** | Returns 409 `currently in non creating, retry after its complete`. Retry with backoff. | [MS Learn § Concurrent operations](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts) |
| **Permissions to create / delete caphost** | `Contributor` on the Foundry account. | [MS Learn § Prerequisites](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts) |
| **Permissions to wire BYO connections** | `User Access Administrator` or `Owner` (for assigning RBAC on the BYO resources). | [MS Learn § Prerequisites](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts) |
| **API version** | `2025-06-01` is the current canonical version this skill targets. | [MS Learn REST examples](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts) |
| **Project caphost connection refs are by name, not resource ID** | `threadStorageConnections` / `vectorStoreConnections` / `storageConnections` / `aiServicesConnections` are arrays of **connection names** that already exist on the project. | [MS Learn § Required properties](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts) |

## 5. Inspect: query caphost state before any change

> **Always inspect before mutating.** The one-per-scope constraint and the
> no-update rule mean an idempotent PUT only behaves "idempotently" if you know
> what's already there. Read first, decide second.

### 5.1 List account-level capability hosts

```http
GET https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{accountName}/capabilityHosts?api-version=2025-06-01
```

Equivalent `az` (works for any user with `Cognitive Services Contributor`):

```bash
az rest --method get \
  --url "https://management.azure.com/subscriptions/${SUB}/resourceGroups/${RG}/providers/Microsoft.CognitiveServices/accounts/${ACCT}/capabilityHosts?api-version=2025-06-01" \
  --query "value[].{name:name, state:properties.provisioningState, kind:properties.capabilityHostKind}"
```

Expected shapes:

- `value: []` — no account caphost exists. You cannot create a project caphost
  until one does (§ 4 prerequisite). Go to § 6 to create one.
- `value: [{name: "default", state: "Succeeded", kind: "Agents"}]` — healthy.
  Safe to operate on the project caphost.
- `value: [{state: "Creating"}]` — operation in flight. Do NOT issue another PUT;
  poll the operation result (§ 5.3) until terminal.
- `value: [{state: "Failed"}]` — broken. DELETE it (§ 7), then recreate.

### 5.2 List project-level capability hosts

```bash
az rest --method get \
  --url "https://management.azure.com/subscriptions/${SUB}/resourceGroups/${RG}/providers/Microsoft.CognitiveServices/accounts/${ACCT}/projects/${PROJ}/capabilityHosts?api-version=2025-06-01" \
  --query "value[].{name:name, state:properties.provisioningState, thread:properties.threadStorageConnections, vector:properties.vectorStoreConnections, storage:properties.storageConnections, ai:properties.aiServicesConnections}"
```

### 5.3 Poll an in-flight operation

Capability-host PUT/DELETE return an `Azure-AsyncOperation` header with a URL of
this shape:

```
https://management.azure.com/subscriptions/{subId}/providers/Microsoft.CognitiveServices/locations/{location}/operationResults/{operationId}?api-version=2025-06-01
```

Poll it (5-second interval, 15-minute budget — covers documented p99) until
`properties.status` is `Succeeded` or `Failed`. **Do not issue a parallel PUT or
DELETE on the same scope while an operation is `Running`** — you'll get the
`currently in non creating, retry after its complete` 409 (§ 6).

## 6. Create: idempotent PUT pattern with retry

### 6.1 Account capability host

```http
PUT https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{accountName}/capabilityHosts/{name}?api-version=2025-06-01

{
  "properties": {
    "capabilityHostKind": "Agents"
  }
}
```

(For VNet-injected accounts, the `customerSubnet` is set at deploy time by
[`foundry-vnet-deploy`](../foundry-vnet-deploy/SKILL.md). This skill operates on
the caphost after that subnet binding already exists; it does not re-bind the
subnet.)

### 6.2 Project capability host

```http
PUT https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{accountName}/projects/{projectName}/capabilityHosts/{name}?api-version=2025-06-01

{
  "properties": {
    "capabilityHostKind": "Agents",
    "threadStorageConnections": ["my-cosmosdb-conn"],
    "vectorStoreConnections":   ["my-aisearch-conn"],
    "storageConnections":       ["my-storage-conn"],
    "aiServicesConnections":    ["my-azure-openai-conn"]
  }
}
```

The four `*Connections` arrays are **connection names** that already exist on the
project (or are inherited from account-level), per MS Learn § "Project capability
host required properties". Wrong-name → 400. Resource IDs in place of names → 400.

### 6.3 The retry-on-409 contract

Three distinct 409 responses, three different handling rules (per MS Learn
§ "HTTP 409 Conflict errors"):

```python
# Python pseudocode using azure-mgmt-cognitiveservices
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.core.exceptions import HttpResponseError
import time

def put_caphost_idempotent(client, rg, acct, name, body, *, max_retries=6, backoff_s=30):
    """Idempotent caphost PUT with 409-class-aware retry.

    Per MS Learn:
      - 200 on same-name + same-config (returns existing)
      - 400 on same-name + different config (no PATCH; delete + recreate)
      - 409 'existing Capability Host with name <other>' — different name at occupied scope
      - 409 'currently in non creating' — concurrent op; retry with backoff
    """
    for attempt in range(max_retries):
        try:
            poller = client.capability_hosts.begin_create_or_update(
                resource_group_name=rg,
                account_name=acct,
                capability_host_name=name,
                capability_host=body,
            )
            return poller.result()
        except HttpResponseError as e:
            msg = (e.message or "").lower()
            if "currently in non creating" in msg:
                # Concurrent-op 409 — wait + retry
                if attempt == max_retries - 1:
                    raise RuntimeError(f"caphost {name} still busy after {max_retries} retries") from e
                time.sleep(backoff_s)
                continue
            if "existing capability host with name" in msg:
                # Different-name 409 — this is policy, not transient. Caller decides.
                raise
            if "differs from the current configuration" in msg or "bad request" in msg:
                # 400 same-name + different-config — caller must delete first
                raise
            raise
```

### 6.4 What a 200-on-replay looks like

If you `PUT` the same name with the same body twice, the second call returns
**200 OK** with the existing resource per MS Learn § "Understand idempotent
behavior". This is what makes the retry above safe: if a transient network blip
hides the success of attempt N, attempt N+1 returns 200 against the now-existing
resource. Field-verified in the catalog fixture
(`skills/foundry-caphost-lifecycle/test-fixture/consumer_prompt.md` step 4).

## 7. Delete: caphost-only (lightweight, keeps account)

### 7.1 When to use this path

DELETE the capability host (without deleting the parent account) when:

- You need to **change a connection reference** (Cosmos, Search, Storage, AOAI)
  on a project caphost. MS Learn is explicit that updates are not supported, so
  the only path is DELETE + recreate.
- You're tearing down agents for a project but want to keep the Foundry account,
  models, other projects, etc.
- The caphost is in `Failed` or stuck `Updating` state and you need a clean slate.

### 7.2 DELETE caphost REST

```http
DELETE https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{accountName}/capabilityHosts/{name}?api-version=2025-06-01
```

(For project scope, insert `projects/{projectName}/` between `accounts/{accountName}/`
and `capabilityHosts/`.)

The response is 202 with an `Azure-AsyncOperation` header. Poll per § 5.3 until
`Succeeded` (typical: 30s-2min; p99 ~5min). Then verify with GET — expect 404.

```bash
# verify gone
az rest --method get \
  --url "https://management.azure.com/subscriptions/${SUB}/resourceGroups/${RG}/providers/Microsoft.CognitiveServices/accounts/${ACCT}/capabilityHosts/${NAME}?api-version=2025-06-01"
# expect HTTP 404 ResourceNotFound
```

### 7.3 What DELETE caphost DOES free

- The caphost resource itself (the per-scope `Microsoft.CognitiveServices/accounts/capabilityHosts` object).
- The project's runtime binding to the listed connections.
- After deletion, agents in that project will no longer have access to the BYO
  thread/file/vector resources the caphost pointed to (MS Learn § "Delete
  capability hosts" Warning).

### 7.4 What DELETE caphost DOES NOT free (field-verified)

- The `serviceAssociationLink` on the agent subnet (only account purge does — § 8).
- The hidden Microsoft.App `Managed Environment` resource that the caphost
  provisioned to host agent compute (only account purge does — § 8).
- Any account-level RBAC or connection definitions.
- Soft-delete state on the account if the account itself is soft-deleted.

This asymmetry is the single biggest gotcha in Foundry Day-2 ops. If you delete
the caphost expecting to redeploy a new one into the same agent subnet, you will
hit `Subnet already in use` on the next deploy — see § 9.

## 8. Soft-delete + purge: full account teardown

### 8.1 Why this matters (the rule)

> **Field-verified rule:** the `serviceAssociationLink` (SAL) that a VNet-injected
> Foundry account holds on its agent subnet is **only released when the parent
> `Microsoft.CognitiveServices/accounts` resource is fully purged** — not when
> the capability host is deleted, and not when the account is soft-deleted. If
> you intend to redeploy into the same subnet, you MUST complete the soft-delete
> + purge sequence below.

This is true for **any** Cognitive Services account with `kind=AIServices` that
had a VNet-injected capability host, not just Foundry. The SAL is created by the
`Microsoft.App` resource provider on behalf of the agent runtime; releasing it
requires the upstream account to be fully removed from soft-delete.

### 8.2 Verified GA CLI sequence

```bash
# Step 1: soft-delete the account (48h recovery window opens)
az cognitiveservices account delete \
  -n "$ACCT" \
  -g "$RG"

# Step 2: confirm the account is in the soft-deleted index
az cognitiveservices account list-deleted -l "$LOC" \
  --query "[?name=='${ACCT}'].{name:name, deletionDate:deletionDate, location:location}"

# (Optional, for explicit confirmation by name)
az cognitiveservices account show-deleted -l "$LOC" -n "$ACCT" -g "$RG"

# Step 3: purge — releases the SAL, the Managed Environment, and the account name
az cognitiveservices account purge -l "$LOC" -n "$ACCT" -g "$RG"

# Step 4: confirm the account is no longer in the soft-deleted index
az cognitiveservices account list-deleted -l "$LOC" \
  --query "[?name=='${ACCT}'].name"
# expect: [] (empty)
```

All four commands are verified GA — no `--preview` flag, no extension required.

### 8.3 What purge releases (field-verified)

After `az cognitiveservices account purge` succeeds:

- The `serviceAssociationLink` on the agent subnet is released within 1-3 minutes.
- The hidden Microsoft.App `Managed Environment` resource is deleted.
- The account name is reclaimable (a new account can take the same name and
  custom domain).
- All capability hosts attached to the account are gone with it (no need to
  delete them separately first).
- Private endpoints owned by the account are deleted.

### 8.4 Verify the subnet binding is released

After purge completes, confirm the agent subnet is reclaimable before attempting
redeploy:

```bash
az network vnet subnet show \
  -g "$VNET_RG" --vnet-name "$VNET" -n "$AGENT_SUBNET" \
  --query "{name:name, sal:serviceAssociationLinks, delegations:delegations[].serviceName}"
```

After purge the `sal` field should be `null` or `[]` (it was a populated array
pointing at `Microsoft.App/environments/<id>` before). The `delegations` array
will still show `Microsoft.App/environments` — that's the subnet delegation, not
the SAL, and it's fine to leave in place for the redeploy.

### 8.5 Timing budget

| Step | Typical | p99 |
|---|---|---|
| Account soft-delete | 30s-2min | 5min |
| Soft-delete index lag (list-deleted ↔ show-deleted consistency) | 5-15s | 60s |
| Purge | 1-3min | 10min |
| SAL release after purge `Succeeded` | 30s-2min | 5min |

Budget at least 20 minutes for the full sequence end-to-end before you call it
hung.

## 9. The redeploy-after-teardown guard

### 9.1 Symptom

```
ERROR: Deployment template validation failed:
'Subnet AgentSubnet of virtual network <vnet-id> is already in use by
serviceAssociationLink <sal-name>. In order to use this subnet, please
remove the existing serviceAssociationLink ...'
```

(Variants seen in the field: `SubnetIsFull`, `SubnetInUse`, references to
`Microsoft.App/environments` in the SAL name, or the bare ARM error
`Subnet already in use`.)

### 9.2 Root cause

The previous Foundry account that bound this subnet still owns the SAL — either
because:

1. **The account is soft-deleted but not purged.** Most common. `az cognitiveservices account list-deleted -l <loc>` shows the old account; the 48h window is still open.
2. **The caphost was deleted but the account was never deleted.** The account
   still exists and still holds the SAL via its hidden Managed Environment.
3. **Another active Foundry account in the same subscription is bound to the
   same subnet.** One subnet, one SAL, one account binding — this is by design.

### 9.3 Fix (matches the cause)

| Cause | Fix |
|---|---|
| Soft-deleted but not purged | `az cognitiveservices account purge` per § 8.2 step 3 |
| Account still exists | Decide: keep it (route redeploy to a new subnet) OR delete + purge it |
| Another active account | Choose a different agent subnet; one subnet per Foundry agent runtime |

After the fix, confirm via § 8.4 that the SAL is gone, then re-run the deploy.

### 9.4 Prevention (teardown discipline)

If you are writing or owning a teardown script for a VNet-injected Foundry account,
the script MUST include the purge step. Account-delete-only is **incomplete**:

```bash
# WRONG — leaves the SAL bound for 48 hours
az cognitiveservices account delete -n "$ACCT" -g "$RG"

# CORRECT — soft-delete + immediate purge
az cognitiveservices account delete -n "$ACCT" -g "$RG"
az cognitiveservices account purge  -l "$LOC" -n "$ACCT" -g "$RG"
```

If you ever want the 48h safety net (e.g. for production rollback safety), keep
the two steps separated by an explicit confirmation gate — but never ship a
"teardown" that stops at soft-delete and calls itself done.

## 10. Soft-delete recovery (within 48h)

If you soft-deleted an account by mistake — or if a teardown script ran in the
wrong subscription — there is a 48-hour window to recover the account intact.

### 10.1 When to recover vs purge

| Situation | Action |
|---|---|
| Wrong account torn down; restore expected | Recover — within 48h, before purge |
| Intentional teardown, full reclaim needed | Purge — § 8 |
| Need to redeploy with same name AND keep history | Recover (cannot do both with purge) |
| Need to redeploy into same agent subnet | Purge (recovery preserves the SAL binding) |

### 10.2 Recover

```bash
# Verify the account is still in the soft-deleted index AND within 48h
az cognitiveservices account show-deleted -l "$LOC" -n "$ACCT" -g "$RG" \
  --query "{name:name, deletionDate:deletionDate, scheduledPurgeDate:scheduledPurgeDate}"

# Recover
az cognitiveservices account recover -l "$LOC" -n "$ACCT" -g "$RG"
```

After recovery, the account is back online with all child resources (including
the capability host) intact and the SAL still bound to the original subnet. The
`scheduledPurgeDate` from `show-deleted` tells you exactly how much time you
have left in the window.

## 11. Anti-patterns

These are mistakes the catalog has paid for in the field. Do not repeat them.

| Anti-pattern | Why it bites |
|---|---|
| Deleting the capability host and expecting the agent subnet to become reusable | DELETE caphost does NOT release the SAL — only account purge does (§ 7.4, § 8). |
| Trying to PATCH / update a caphost in-place | No update API exists. Same-name + different config returns 400 (§ 4). Use DELETE + recreate. |
| Reusing the same caphost name across different configurations | Returns 400 on the second PUT. Either keep the original config OR DELETE first. |
| Creating a project caphost without an account caphost first | Returns 409 — account caphost is a hard prerequisite (§ 4). |
| Issuing concurrent PUTs against the same scope | Returns 409 `currently in non creating`. Use the polling pattern (§ 5.3) instead. |
| Teardown that stops at `az cognitiveservices account delete` | Leaves the SAL bound for 48h. Next redeploy into the same subnet fails (§ 9.4). |
| Running `az cognitiveservices account purge` without first running `list-deleted` to confirm presence | Purge of a non-existent soft-deleted account returns a misleading 404. Always confirm soft-delete first (§ 8.2). |
| Trying to `recover` an account that's already past its 48h `scheduledPurgeDate` | Returns 404 — the account is permanently gone, just not yet swept from the index. Treat as purged. |
| Reading the capability host state without first checking the parent account's `provisioningState` | If the account itself is `Failed` or `Deleting`, every caphost call returns a confusing 500/404 cascade. Inspect the account first. |
| Assuming `az` CLI works for capability host CRUD | There is no `az cognitiveservices account capability-host` group as of 2025-06-01. Use `az rest` or the `azure-mgmt-cognitiveservices` SDK. |

## 12. Cross-references

- [`foundry-vnet-deploy`](../foundry-vnet-deploy/SKILL.md) — greenfield BYO-VNet
  Foundry deploy that creates the account, project, capability host, and subnet
  bindings this skill operates on at Day-2.
- [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) — azd-template
  hosted-agent flow on top of an already-deployed Foundry account.
- [`azure-tenant-isolation`](../azure-tenant-isolation/SKILL.md) — mandatory
  two-layer guard before issuing destructive operations (account delete / purge)
  across multi-subscription / multi-tenant environments.
- [`citadel-spoke-onboarding`](../citadel-spoke-onboarding/SKILL.md) — if your
  account is a Citadel spoke, see this skill for the broader app-layer onboarding
  contract before purging.
- MS Learn — [Capability hosts](https://learn.microsoft.com/azure/foundry/agents/concepts/capability-hosts) — the authoritative source for the create-time REST contract.
- MS Learn — [Set up private networking for Foundry Agent Service](https://learn.microsoft.com/azure/foundry/agents/how-to/virtual-networks) — the VNet-injection background that explains why the SAL exists in the first place.
- Azure CLI — [`az cognitiveservices account`](https://learn.microsoft.com/cli/azure/cognitiveservices/account) — `delete`, `purge`, `recover`, `list-deleted`, `show-deleted` reference.

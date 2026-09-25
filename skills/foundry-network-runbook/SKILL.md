---
name: foundry-network-runbook
description: >
  Operational runbook for diagnosing Microsoft Foundry **network-layer**
  failures after a deploy succeeds — DNS, VNet peering, NSG / Azure
  Firewall denies, RBAC scope, capability host subnet exhaustion, agent
  NIC / MI provisioning, project-connection status.

  USE FOR: foundry network 503, InvalidPrivateDnsZoneIds at deploy,
  Subnet already in use by capability host, agent inference 503,
  inference timeout no response, private endpoint not resolving,
  Resolve-DnsName returns public IP from spoke, NSG deny Foundry agent
  subnet, AzureFirewall deny Foundry, 403 Managed Identity Operator,
  hosted agent NIC provisioning 403, VNet peering Disconnected, project
  connection red in portal, APIM private DNS not linked, SAL stale.

  DO NOT USE FOR: telemetry (use foundry-observability); Day-0 deploy
  (use foundry-vnet-deploy); Day-2 caphost lifecycle / purge (use
  foundry-caphost-lifecycle); APIM / cross-region (use
  foundry-cross-resource); Citadel JWT 403 (use
  citadel-spoke-onboarding); SDK; quota; cost.
metadata:
  version: "1.1.1"
---

# Foundry Network Runbook — Diagnose connectivity failures after the deploy succeeds

## 1. Goal

This runbook is for the on-call engineer who just got the page **"Foundry
agent is up but inference / project connection / model call is failing
over the network."** The `foundry-vnet-deploy` succeeded (or the
`foundry-caphost-lifecycle` create returned `Succeeded`), the resources
exist in the portal — but something at the **network layer** is wrong:
DNS resolves to the wrong IP, an NSG drops the packet, an RBAC role is
missing for a private DNS zone, a VNet peering went `Disconnected`, the
caphost subnet is wedged. You have ≤ 30 minutes to isolate the layer
before escalating.

An inbound private endpoint does **not** configure agent egress. An approved
endpoint or a successful ARM deployment is not proof that the agent can reach
its tool privately. Start with the caller and traffic path in § 3, not a
firewall change based on the HTTP status alone.

This runbook is **not** a telemetry guide (`foundry-observability`
covers App Insights + OTel wiring), not a deploy guide
(`foundry-vnet-deploy` covers Day-0; `foundry-caphost-lifecycle` covers
Day-2 lifecycle), not an auth / JWT troubleshoot for the Citadel APIM
gateway (that's `citadel-spoke-onboarding`), and not an SDK / quota
troubleshoot. If the symptom is not a network-layer symptom, jump to
§ 8 — the cross-reference index points you at the right skill.

## 2. When to use this runbook

Trigger this runbook when **all** of the following are true:

1. The Foundry deployment (or hosted-agent create, or caphost create)
   reported `Succeeded` in ARM and the resources are visible in the
   portal.
2. Something fails downstream with a suspected network-layer symptom: 503 from inference,
   DNS resolving to a public IP, project connection showing red, a
   private endpoint missing or not approved, an MCP connector error with no
   observed destination request, or a fresh redeploy hitting `Subnet already in use`.
3. You have a baseline of "this worked yesterday" or "the deploy just
   completed, why doesn't it work now?" — i.e., the failure mode is
   **operational** (post-deploy), not a code or SDK bug.

If the failure is during the Bicep `az deployment group create` itself,
use `foundry-vnet-deploy § 10b` (safe retry). If the failure is a
hosted-agent-creation 403 with `MI provisioning failed` or
`NIC provisioning failed`, this runbook's § 4 matrix points you back to
`foundry-vnet-deploy § 8b` for the RBAC fix.

## 3. Pre-flight checklist

Select the [versioned hosted contract](../foundry-hosted-agents/references/hosted-contract.json)
and its early capability/permission gate before dependent work. Distinguish
invoke permission from version, session and response retrieval rights for the
actual reader. Use finite per-I/O deadlines as well as a diagnostic objective;
a stalled tool does not establish an Azure failure. Preserve original operation
IDs and UNKNOWN under the [recovery contract](../foundry-hosted-agents/references/operation-recovery.md).

Capture this baseline **before** you start diagnosing. Without it you
will mis-attribute symptoms (e.g., blaming DNS when the real failure is
a peering that went `Disconnected` 10 minutes earlier).

### 3.1 Identify the caller and network model

Apply [`azure-tenant-isolation`](../azure-tenant-isolation/SKILL.md) before any
Azure command. Record the approved tenant/subscription, resource owners, selected
Basic/Standard setup, BYO/Managed network, agent type and failing destination.
The commands below describe BYO VNet; do not apply subnet/SAL assumptions to
Managed VNet. Reuse an existing approved diagnostic host; do not deploy a VM or
open a public endpoint just to investigate.

| Path | What must be observed | What does not prove it |
|---|---|---|
| SDK client or browser/Playground → Foundry | The actual caller's DNS resolver, route, TLS and authenticated data-plane request to the intended Foundry endpoint | ARM success, a PE approval, or a test from another machine |
| Hosted agent's own code → model/API | The actual hosted runtime's injected-network route and destination access | A laptop or VM `curl` |
| Platform tool call → private MCP/data service | Tool/data-proxy path, project capability host, destination connectivity and tool authentication | Successful ingress to Foundry or hosted code reaching a different endpoint |

For prompt agents there is no hosted Micro VM on the request path. Reuse the
[traffic-path reference](../foundry-vnet-deploy/references/agent-networking.md#1-two-traffic-paths-hosted-vs-prompt-agents)
and [tool reachability matrix](../foundry-vnet-deploy/references/agent-tools-network-isolation.md#1-tool-reachability-matrix).
Network injection does not make public-endpoint tools private or establish a
deny-all-public-egress policy.

Record observations with time, endpoint, caller location, approved identity and
request/tool-call correlation. Keep tokens and customer payloads out of logs.
Missing permissions or an unavailable private probe location mean **NOT_TESTED**,
not a successful check and not permission to change resources.

### 3.2 Read-only baseline

Run the 7 checks below in the approved context, marking topology-specific checks
not applicable only with a recorded reason. `SUB` is the workload subscription;
`DNS_SUB` and `DNS_RG` identify the zone owner, which may be different. Use the
owner's resource group/subscription for each zone when they are split. `VNET_RG`
is the VNet resource group. None of these checks authorize remediation.
For an existing account/subnet, the canonical
[read-only network inventory](../foundry-vnet-deploy/SKILL.md#step-9a-read-only-network-inventory)
can collect the account-side PE and subnet observations. Reuse it rather than
creating another helper; its `runtime_connectivity: NOT_TESTED` remains valid
even when all its control-plane checks pass.

```bash
# 1. VNet peerings (spoke side): all MUST be Connected
az network vnet peering list \
  -g "$VNET_RG" --vnet-name "$VNET" --subscription "$SUB" \
  --query "[].{name:name, state:peeringState, remote:remoteVirtualNetwork.id}" \
  -o table
```

```bash
# 2. Private DNS zone inventory (existence is not proof of resolution)
az network private-dns zone list \
  -g "$DNS_RG" --subscription "$DNS_SUB" \
  --query "[].{name:name, vnetLinks:numberOfVirtualNetworkLinks, records:numberOfRecordSets}" \
  -o table
```

```bash
# 3. Private endpoints in the spoke RG and their approval status
az network private-endpoint list -g "$RG" --subscription "$SUB" \
  --query "[].{name:name, target:privateLinkServiceConnections[0].privateLinkServiceId, status:privateLinkServiceConnections[0].privateLinkServiceConnectionState.status}" \
  -o table
```

```bash
# 4. Foundry account network state (public access + injection subnet)
az rest --method GET \
  --url "https://management.azure.com/subscriptions/${SUB}/resourceGroups/${RG}/providers/Microsoft.CognitiveServices/accounts/${ACCT}?api-version=2025-04-01-preview" \
  --query "{public:properties.publicNetworkAccess, injections:properties.networkInjections}" -o json
```

```bash
# 5. Project MI roles for platform-managed operations and BYO dependencies
PRINCIPAL_ID=$(az rest --method GET \
  --url "https://management.azure.com/subscriptions/${SUB}/resourceGroups/${RG}/providers/Microsoft.CognitiveServices/accounts/${ACCT}/projects/${PROJ}?api-version=2025-04-01-preview" \
  --query "identity.principalId" -o tsv)

az role assignment list --assignee "$PRINCIPAL_ID" --all --subscription "$SUB" \
  --query "[].{role:roleDefinitionName, scope:scope}" -o table
```

```bash
# 6. Agent subnet binding (serviceAssociationLink + delegation)
az network vnet subnet show \
  -g "$VNET_RG" --vnet-name "$VNET" -n "$AGENT_SUBNET" --subscription "$SUB" \
  --query "{name:name, sal:serviceAssociationLinks, delegations:delegations[].serviceName}"
```

```powershell
# 7. Set $ACCT in this PowerShell session to the approved account name.
# Run from the failing caller's approved private network, not an unrelated host.
Resolve-DnsName "${ACCT}.services.ai.azure.com"
Resolve-DnsName "${ACCT}.openai.azure.com"
Resolve-DnsName "${ACCT}.cognitiveservices.azure.com"
# Compare the CNAME/A answers with the intended PE's actual private addresses.
# An arbitrary private IP is not sufficient; repeat for the failing tool FQDN.
```

The PE listing is a summary of the first automatic connection in the selected
resource group, not a complete topology inventory. Inspect the intended PE,
including manual connections, target/subresource, approval, NIC addresses and DNS
zone group; a PE in another resource group is not missing. Confirm the group's
records actually exist. The three Foundry zones are not the entire dependency
set: Standard adds Search/Blob/Cosmos; Basic has its own Monitor/optional ACR
zones. Use the [selected template's DNS map](../foundry-vnet-deploy/SKILL.md#step-0-choose-the-template-decision-guide).

Also inspect the exact **project** capability host through the
[shared preflight](../foundry-hosted-agents/references/deployment-preflight.md#scope-before-action):
Basic requires an `Agents`/`Succeeded` project host without BYO arrays; Standard
requires the account host/subnet and project host with the approved BYO connection
names. Do not invent a customer-created account-host prerequisite for Basic.
Use GET, not PUT as a probe. Failed, incomplete or forbidden reads are unknown,
not an empty inventory.

The project MI is not necessarily the identity of every outbound request.
Distinguish the operator, project MI, hosted-agent identity and delegated user
where applicable; check roles for the actual operation and target scope.
If a baseline check shows an anomaly, use § 4 to narrow it before proposing a fix.

### 3.3 Evidence for private ingress and agent egress

| Check | Required evidence | Insufficient evidence |
|---|---|---|
| Positive ingress | From the intended private caller: expected PE DNS answer, TCP/TLS success and a successful authenticated Foundry data-plane response | HTTP 200 alone, or a control-plane GET |
| Negative ingress | From an approved caller outside the private route, with otherwise valid authentication: rejection attributable to public-network restrictions, retaining the service error code/body | Any 403, `AuthenticationTypeDisabled`, missing RBAC, or a laptop still using VPN/private proxy |
| Agent egress | A real agent invocation that actually calls the required tool, correlated with destination-side request/access logs and the expected private route | Agent prose claiming success, a VM-only test, or a successful tool health endpoint |

For MCP, retain the relevant `initialize`, `tools/list` and `tools/call` evidence;
initialization/listing may belong to an existing reused session. Do not force an
extra handshake or disable authentication merely to obtain logs. A logged socket
peer identifies the **immediate hop**: account for APIM, ingress proxies, firewall
SNAT and trusted forwarding configuration before attributing it to an agent
subnet. Do not trust an arbitrary forwarded-IP header.

These checks prove the observed paths, not that every public destination is
blocked. A deny-by-default egress requirement needs separate policy review and an
explicitly authorized negative test. Keep unobserved paths **NOT_TESTED**. Reuse
the hosted preflight's evidence contract rather than inventing a new PASS schema.

## 4. Symptom → cause → fix matrix

Network-layer symptoms and look-alikes only. A status code or missing application
log is not a unique root cause. The Fix column is a proposed next action for the
resource owner, never authorization to grant roles, change NSGs/DNS, open public
access, delete hosts or purge accounts. For SDK / quota issues see § 8.

| Symptom | Likely cause | Diagnostic | Fix |
|---|---|---|---|
| `InvalidPrivateDnsZoneIds` at deploy time | Wrong zone ID/owner scope, nonexistent zone or insufficient deployment-principal access | Check the selected template's zone map, zone existence and effective permissions in the DNS subscription (§ 5) | Ask the DNS owner to correct the mapping or authorize narrowly scoped access; do not recreate central zones. |
| `Subnet already in use by capability host` on redeploy | Existing live or stale capability-host binding | Read subnet SAL and account/project hosts; determine ownership before classifying the binding as stale | Follow `foundry-caphost-lifecycle § 9`; destructive recovery under § 8 requires separate approval. A non-empty SAL alone never authorizes purge. |
| Inference 503 with no App Insights trace | Runtime readiness, tool/data-proxy failure or network failure; telemetry may also be absent | Identify the failing hop, inspect project host/readiness and then the intended PE/DNS path (§ 3) | Resolve the observed layer; missing telemetry is not proof that the PE is missing. Use § 8 for container/SDK failures. |
| `400 external_connector_error` containing `Server returned 424`, no observed MCP request | Missing/unready project host or its dependencies is one candidate; DNS/routing, TLS and connector errors can also prevent arrival | Inspect the project host by GET and the mode-specific preflight; distinguish this from hosted `session_not_ready`. Correlate destination logs before checking NSG/firewall flows | Reuse the existing Basic/Standard preflight and lifecycle path. No automatic host creation, account rebuild or firewall relaxation. |
| TCP timeout or TLS failure to the intended destination | Route/NSG/firewall deny, wrong DNS target, or certificate/TLS inspection problem | Separate DNS, TCP and TLS; inspect effective routes, applicable NSG/PE network policies, firewall logs and the certificate chain from the failing path | Have the owner propose only the required route/rule/inspection correction. Do not disable TLS verification or assume a default route forces PE traffic through the firewall. |
| DNS returns a public/wrong private IP, `NXDOMAIN` or `SERVFAIL` | Wrong resolver path, missing zone link/group/A record, stale cache or forwarding loop | Compare all relevant FQDN answers with intended PE addresses; inspect the actual client's resolver, including VPN/browser behavior, and the hybrid chain (§ 5) | Correct the specific record/link/forwarder with its owner; do not create a shadow public zone or add hosts entries as a permanent fix. |
| Hosted-agent MI/NIC provisioning 403 or subnet delegation error | Caller permissions, wrong/missing delegation, provider registration or an incompatible subnet | Read the exact ARM error, caller identity/scope and subnet delegation. Check required providers, including `Microsoft.App` and `Microsoft.ContainerService`, against the official prerequisites | Use `foundry-vnet-deploy` prerequisites and § Step 8b for owner-approved repair; do not grant broad roles or change a shared subnet speculatively. |
| APIM 404 / 503 from a Foundry call | DNS/routing to APIM, gateway API/policy configuration or backend failure | Identify which hop returned the response; check APIM DNS/TLS and correlated gateway/backend logs | Use `citadel-spoke-onboarding` after confirming the private route; an HTTP status alone does not prove a missing APIM DNS link. |
| Project connection red or Storage/Cosmos/Search 403 | Network restriction, token audience/authentication type or missing effective data-plane authorization | Preserve the service error code; check actual destination route/PE approval and the calling identity's target-scoped roles, including Cosmos native SQL roles | Network and authorization are separate checks. `publicNetworkAccess: Enabled` is a posture issue, not itself the cause of a 403; do not toggle it as a fix. |
| VNet peering `Disconnected` | Missing/changed reverse peering or incompatible address-space configuration | Read both sides and current address spaces; verify effective routing with the network owner | Reconcile the intended topology before an approved repair. Do not delete and recreate peerings as a diagnostic. |

> **Matrix discipline.** The matrix is **deliberately capped at 10
> rows**. If a symptom is application-layer (model returns wrong text,
> SDK raises a TypeError, AppInsights shows the call but with bad data),
> it goes in § 8, not here.

## 5. Pre-flight at scale (cross-subscription DNS)

When the spoke is deployed into an enterprise hub-and-spoke topology,
private DNS zones are typically owned by the **platform
team in a separate connectivity hub subscription**. The deployment
principal needs RBAC in **both** subscriptions — one for the spoke
resources, one for the hub PDZs — or the deploy fails with
`InvalidPrivateDnsZoneIds`. The six-zone set below describes Standard; use
Basic's Monitor/optional ACR map when selected, adding APIM only when applicable.
This is the canonical hub-and-spoke pattern
documented in [CAF — Private Link and DNS integration at scale](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/private-link-and-dns-integration-at-scale#private-link-and-dns-integration-in-hub-and-spoke-network-architectures).

| Subscription | Resource | Required role | Why |
|---|---|---|---|
| Spoke (workload) | Spoke resource group | `Contributor` (or finer-grained `Cognitive Services Contributor` + `Network Contributor`) | Deploy the AI Services account, project, model deployment, spoke VNet, PEs, NICs |
| Spoke (workload) | Spoke VNet | `Network Contributor` | Subnet delegation `Microsoft.App/environments`, PE NIC injection, agent NIC creation |
| Hub (connectivity) | Each of the 6 `privatelink.*` PDZs (or `privatelink.azure-api.net` if Citadel) | `Private DNS Zone Contributor` (per-zone, NOT RG-wide) | Create the VNet link from each zone to the spoke VNet so `Resolve-DnsName` from the spoke returns private IPs |
| Hub (connectivity) | Hub VNet | `Network Contributor` (on the hub side, for the hub team) | Create the **reverse** hub→spoke peering (Citadel only — see `foundry-vnet-deploy § 8d`) |
| Foundry account scope | The AI Services account | `Managed Identity Operator` (caller of hosted-agent create) | Per-user grant; provisioning of agent-instance MIs |
| Agent subnet scope | The injection subnet | `Network Contributor` (caller of hosted-agent create) | Per-user grant; agent NIC creation in the delegated subnet |

If the deploy fails with `InvalidPrivateDnsZoneIds`, inspect the approved
**hub subscription** explicitly, without switching the global CLI default.
This is one zone; repeat for each zone in the selected deployment:

```bash
az role assignment list \
  --assignee "$DEPLOYER_OBJECT_ID" \
  --subscription "$HUB_SUB" --include-inherited \
  --scope "/subscriptions/${HUB_SUB}/resourceGroups/${HUB_DNS_RG}/providers/Microsoft.Network/privateDnsZones/privatelink.cognitiveservices.azure.com" \
  -o table
```

An empty direct/inherited listing is not an automatic grant request: have the
owner verify group membership, custom roles, conditions and the actual denied
operation. Any required grant needs explicit approval at the narrowest applicable
scope; allow propagation before retrying the original operation.

### Hybrid DNS: on-premises, VPN and custom resolvers

For corporate callers, trace **client → corporate DNS → Azure DNS Private
Resolver inbound endpoint (or existing Azure-hosted forwarder) → Azure DNS →
linked private zone**. `168.63.129.16` is an Azure-internal resolver address,
not an on-premises DNS target reachable over VPN/ExpressRoute.

Configure conditional forwarding for the recommended **public service
namespaces** toward the Azure resolver, not a blanket `privatelink.*`-only rule.
For Foundry these are `services.ai.azure.com`, `openai.azure.com` and
`cognitiveservices.azure.com`; add the documented namespaces for actual
dependencies. Conditional forwarding is not an authoritative public-zone
override: keep the Azure-managed `privatelink.*` zones and their PE records.
See [Private Endpoint DNS integration](https://learn.microsoft.com/azure/private-link/private-endpoint-dns-integration#azure-private-resolver-with-on-premises-dns-forwarder).

Check DNS reachability on UDP/TCP 53, links on the resolver/forwarder VNet, the
client's selected DNS servers and the complete CNAME/A chain. Where authorized,
compare an ordinary client lookup with one directed to the inbound resolver:
different results localize a forwarding/cache/client-path problem. Check for
forwarding loops and conflicting private zones before adding another link.
Peering or a connected VPN alone does not configure DNS. A hosts-file override
is at most a temporary, owner-approved diagnostic; it masks the resolver path
and must not count as production DNS validation.

## 6. Diagnostic Kusto queries

The Kusto queries require the matching ingestion/schema in the selected Log
Analytics workspace. A missing table may mean missing ingestion or a different
table mode, not a proven network failure. RBAC query D uses ARM directly.
See `foundry-observability` for telemetry wiring; do not enable new logging
resources without approval.

### A. NSG flow log denies on the agent subnet

```kusto
AzureNetworkAnalytics_CL
| where TimeGenerated > ago(1h)
| where SubType_s == "FlowLog"
| where FlowStatus_s == "D"            // 'D' = denied by NSG
| where SrcIP_s startswith "10."        // adjust to the agent subnet CIDR
   or DestIP_s startswith "10."
| project TimeGenerated, NSGRule_s, SrcIP_s, SrcPort_d,
          DestIP_s, DestPort_d, L7Protocol_s, FlowDirection_s
| order by TimeGenerated desc
| take 50
```

> **Legacy query:** use only when the existing Traffic Analytics schema matches.
> New NSG flow logs cannot be created after June 30, 2025; retirement is
> September 30, 2027. For new coverage, use
> [VNet flow logs](https://learn.microsoft.com/azure/network-watcher/vnet-flow-logs-overview)
> and that deployment's documented schema. A missing legacy table is not a
> reason to try enabling NSG flow logs or to conclude that no traffic occurred.

### B. Azure Firewall denies for Foundry-bound traffic

If the agent subnet egresses through an Azure Firewall (hub-and-spoke
topology), denies show up here:

```kusto
AzureDiagnostics
| where TimeGenerated > ago(1h)
| where Category in ("AzureFirewallApplicationRule", "AzureFirewallNetworkRule")
| where OperationName == "AzureFirewallRuleLog"
| where msg_s contains "Deny"
| where msg_s contains "cognitiveservices.azure.com"
   or msg_s contains "services.ai.azure.com"
   or msg_s contains "openai.azure.com"
| project TimeGenerated, msg_s, Category
| order by TimeGenerated desc
| take 50
```

This query filters Foundry destinations in the legacy `AzureDiagnostics` mode;
it does not cover every MCP, identity or registry endpoint. Use the actual
destination and the firewall's configured table mode when investigating other
hops. Correlate denies with the failing request and have the owner review the
narrow required rule. No matching log is inconclusive if the route bypasses the
firewall, ingestion is delayed or the filter/schema does not cover the flow.

### C. Foundry account `Failed` events from the activity log

When a hosted-agent create or a model deployment fails at the ARM layer
(403, conflict, validation error), this query surfaces the activity-log
trail:

```kusto
AzureActivity
| where TimeGenerated > ago(24h)
| where ResourceProvider == "Microsoft.CognitiveServices"
| where ActivityStatusValue == "Failed"
| project TimeGenerated, OperationNameValue, ActivitySubstatusValue,
          Caller, ResourceId, Properties
| order by TimeGenerated desc
| take 20
```

### D. Role-assignment audit for a given principal (JMESPath, not KQL)

Activity-log-based RBAC audits are slow and lag by minutes. For
real-time RBAC introspection, use the ARM control plane directly
(or see [`foundry-rbac-audit`](../foundry-rbac-audit/) for a Python-
wrapped probe that returns a structured manifest consumable by
sibling-skill flows):

```bash
az role assignment list --assignee "$PRINCIPAL_ID" --all \
  --query "[?contains(roleDefinitionName, 'DNS Zone') || contains(roleDefinitionName, 'Network') || contains(roleDefinitionName, 'Managed Identity') || contains(roleDefinitionName, 'Cognitive Services')].{role:roleDefinitionName, scope:scope}" \
  -o table
```

This display-name filter is a starting point, not an effective-permissions
verdict. Renamed/custom/group-assigned roles may be missed. Inspect the actual
principal, denied action, scope and conditions before proposing a grant.

## 7. Health checks (recurring)

Schedule these as weekly cron checks (or as part of an Azure Function /
Logic App / scheduled Pipeline). They catch slow drift — a peering that
went `Disconnected` overnight, a missing VNet link after a hub team
rotation, public-access flipped back on by a "compliance" pipeline.

```bash
# H1: All spoke peerings must be Connected
az network vnet peering list -g "$VNET_RG" --vnet-name "$VNET" --subscription "$SUB" \
  --query "[].peeringState" -o tsv | sort -u
# Expect: Connected for every planned peering; an empty list is not proof.
```

```bash
# H2: Standard + Azure-provided DNS example; adapt zone/VNet ownership per § 5
for z in privatelink.services.ai.azure.com privatelink.openai.azure.com \
         privatelink.cognitiveservices.azure.com privatelink.search.windows.net \
         privatelink.blob.core.windows.net privatelink.documents.azure.com; do
  found=$(az network private-dns link vnet list \
    -g "$DNS_RG" --zone-name "$z" --subscription "$DNS_SUB" \
    --query "[?virtualNetwork.id=='${SPOKE_VNET_ID}'].provisioningState" -o tsv)
  printf "%-50s %s\n" "$z" "${found:-MISSING}"
done
# Expect: every planned link ends in Succeeded. This does not test DNS records.
```

```bash
# H3: All private endpoints in the spoke RG are Approved
az network private-endpoint list -g "$RG" --subscription "$SUB" \
  --query "[?privateLinkServiceConnections[0].privateLinkServiceConnectionState.status!='Approved'].name" -o tsv
# Empty output is inconclusive if no PEs exist or manual connections are used.
```

```bash
# H4: Public network access disabled on the AI Services account
az rest --method GET \
  --url "https://management.azure.com/subscriptions/${SUB}/resourceGroups/${RG}/providers/Microsoft.CognitiveServices/accounts/${ACCT}?api-version=2025-04-01-preview" \
  --query "properties.publicNetworkAccess" -o tsv
# Expect: Disabled. Enabled = either intentional opening or compliance pipeline flipped it.
```

```bash
# H5: Standard-only ARM role-count heuristic, not a complete RBAC check
PRINCIPAL_ID=$(az rest --method GET \
  --url "https://management.azure.com/subscriptions/${SUB}/resourceGroups/${RG}/providers/Microsoft.CognitiveServices/accounts/${ACCT}/projects/${PROJ}?api-version=2025-04-01-preview" \
  --query "identity.principalId" -o tsv)
az role assignment list --assignee "$PRINCIPAL_ID" --all \
  --query "length([?contains(roleDefinitionName, 'Storage Blob') || contains(roleDefinitionName, 'Cosmos DB') || contains(roleDefinitionName, 'Search')])" -o tsv
# A count is not proof of target scopes/conditions and excludes Cosmos SQL roles.
```

For H5, verify the actual effective assignments and the separate Cosmos SQL role
using `foundry-vnet-deploy § 11.10`; Basic has different dependencies and roles.

```bash
# H6: Agent subnet SAL still bound to the live caphost (not stale-but-not-purged)
az network vnet subnet show \
  -g "$VNET_RG" --vnet-name "$VNET" -n "$AGENT_SUBNET" \
  --query "serviceAssociationLinks[].name" -o tsv
# Compare with the known live host binding; presence or absence alone proves
# neither safe subnet reuse nor a need to purge. Ownership review is mandatory.
```

## 8. Cross-references

This runbook covers **network-layer** symptoms only. For symptoms outside
that scope, follow the pointers below — each one cites a specific
section, not the whole skill.

- **`foundry-vnet-deploy § 11`** (post-deployment verification — 11.1
  through 11.11). Reuse its control-plane observations and runtime evidence.
  A failed or untested connectivity check is a reason to use this runbook,
  not a requirement to finish every check first. Diagnose the failing layer
  rather than classifying all § 11 failures as deploy-time bugs.
- **`foundry-vnet-deploy § Step 8`** (private DNS zones — central DNS
  at scale). Source of truth for the cross-subscription PDZ shape and
  the `dnsZonesSubscriptionId` parameter.
- **`foundry-vnet-deploy § Step 8b`** (hosted-agent developer RBAC).
  Source of truth for the two per-user grants this runbook's § 4
  references for `MI provisioning failed` and `NIC provisioning failed`.
- **[Hosted deployment preflight](../foundry-hosted-agents/references/deployment-preflight.md)**.
  Reuse its Basic/Standard host checks and runtime evidence boundaries. For
  hosted `session_not_ready`, inspect container readiness/startup rather than
  treating every 424 as the MCP connector failure in § 4.
- **`foundry-caphost-lifecycle § 7`** (caphost-only DELETE) and
  **`§ 8`** (full account soft-delete + purge). Recovery paths when
  the agent subnet is wedged with a stale SAL and a redeploy fails with
  `Subnet already in use`.
- **`foundry-caphost-lifecycle § 11`** (anti-patterns). Caphost-specific
  don'ts (don't soft-delete and immediately redeploy; don't update
  caphost connections in place).
- **`foundry-observability`** (telemetry wiring). Application-layer
  diagnostics: App Insights traces from agent SDK calls, OTel spans,
  custom evaluator events. This runbook stops at the network layer.
- **`foundry-cross-resource`** (APIM front, cross-region failover).
  When the diagnostic is "the Foundry endpoint is fine but the APIM
  in front of it is misbehaving across regions".
- **`citadel-spoke-onboarding`** (Citadel-specific JWT 403, APIM
  product policies). 403s from the `*.azure-api.net` host are a
  Citadel concern, not a Foundry-network concern.

## 9. References

- [Cloud Adoption Framework — Private Link and DNS integration at scale](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/private-link-and-dns-integration-at-scale#private-link-and-dns-integration-in-hub-and-spoke-network-architectures) — canonical hub-and-spoke PDZ pattern; the architecture this runbook's § 5 table is derived from.
- [Azure Private Endpoint DNS configuration](https://learn.microsoft.com/azure/private-link/private-endpoint-dns) — authoritative list of `privatelink.*` zone names per Azure resource type; verify the zones for the selected Basic/Standard configuration and dependencies.
- [Foundry — How to use a custom virtual network](https://learn.microsoft.com/azure/foundry/agents/how-to/virtual-networks) — how the AI Services account's `networkInjections` property and the agent subnet delegation `Microsoft.App/environments` fit together.
- [Foundry — Hosted agent permissions](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agent-permissions) — source of truth for the `Managed Identity Operator` + `Network Contributor` grants the § 4 matrix references for hosted-agent create 403s.
- [Azure CLI — `cognitiveservices account`](https://learn.microsoft.com/cli/azure/cognitiveservices/account) — GA reference for the `delete` / `purge` / `list-deleted` / `show-deleted` commands the matrix points at for stale-SAL recovery.
- [NSG flow logs retirement](https://learn.microsoft.com/azure/network-watcher/network-watcher-nsg-flow-logging-overview) — lifecycle limits for the legacy query A; use VNet flow logs for new coverage.
- [Private Endpoint DNS integration](https://learn.microsoft.com/azure/private-link/private-endpoint-dns-integration) — resolver placement, public-namespace conditional forwarding and DNS zone groups.
- [Private Endpoint network policies](https://learn.microsoft.com/azure/private-link/disable-private-endpoint-network-policy) — NSG/UDR applicability and why a default route alone does not prove firewall traversal.
- [Private Endpoint ingress and agent egress field case](https://techcommunity.microsoft.com/blog/AzureArchitectureBlog/your-private-endpoint-does-not-cover-agent-egress-locking-down-azure-ai-foundry-/4547864) — motivates the paired ingress checks and project-host/MCP investigation. Its observed 424 cause is not universal; use current Learn guidance for DNS forwarding and the existing Basic/Standard contracts. This is external case evidence, not live validation of this runbook.

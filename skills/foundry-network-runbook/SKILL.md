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
  version: "1.0.2"
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
2. Something fails downstream at the network layer: 503 from inference,
   DNS resolving to a public IP, project connection showing red, a
   private endpoint missing or not approved, a fresh redeploy hitting
   `Subnet already in use`.
3. You have a baseline of "this worked yesterday" or "the deploy just
   completed, why doesn't it work now?" — i.e., the failure mode is
   **operational** (post-deploy), not a code or SDK bug.

If the failure is during the Bicep `az deployment group create` itself,
use `foundry-vnet-deploy § 10b` (safe retry). If the failure is a
hosted-agent-creation 403 with `MI provisioning failed` or
`NIC provisioning failed`, this runbook's § 4 matrix points you back to
`foundry-vnet-deploy § 8b` for the RBAC fix.

## 3. Pre-flight checklist

Capture this baseline **before** you start diagnosing. Without it you
will mis-attribute symptoms (e.g., blaming DNS when the real failure is
a peering that went `Disconnected` 10 minutes earlier).

Run all 7 commands in order. Each block is read-only — none of them
mutate Azure state.

```bash
# 1. VNet peerings (spoke side): all MUST be Connected
az network vnet peering list \
  -g "$RG" --vnet-name "$VNET" \
  --query "[].{name:name, state:peeringState, remote:remoteVirtualNetwork.id}" \
  -o table
```

```bash
# 2. Private DNS zones reachable from the spoke
az network private-dns zone list \
  -g "$DNS_RG" \
  --query "[].{name:name, vnetLinks:numberOfVirtualNetworkLinks, records:numberOfRecordSets}" \
  -o table
```

```bash
# 3. Private endpoints in the spoke RG and their approval status
az network private-endpoint list -g "$RG" \
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
# 5. Project MI role assignments (the principal the agent runtime runs as)
PRINCIPAL_ID=$(az rest --method GET \
  --url "https://management.azure.com/subscriptions/${SUB}/resourceGroups/${RG}/providers/Microsoft.CognitiveServices/accounts/${ACCT}/projects/${PROJ}?api-version=2025-04-01-preview" \
  --query "identity.principalId" -o tsv)

az role assignment list --assignee "$PRINCIPAL_ID" --all \
  --query "[].{role:roleDefinitionName, scope:scope}" -o table
```

```bash
# 6. Agent subnet binding (serviceAssociationLink + delegation)
az network vnet subnet show \
  -g "$VNET_RG" --vnet-name "$VNET" -n "$AGENT_SUBNET" \
  --query "{name:name, sal:serviceAssociationLinks, delegations:delegations[].serviceName}"
```

```powershell
# 7. DNS resolution FROM INSIDE the spoke (run on a Bastion VM, peered VM,
#    or VPN-connected host — NOT from your laptop over the public internet)
Resolve-DnsName "${ACCT}.cognitiveservices.azure.com"
# MUST return a 10.x / 172.16-31.x / 192.168.x private IP.
# Public IP back = private endpoint missing OR DNS zone not VNet-linked.
```

If any of the 7 baseline checks already shows an anomaly, jump straight
to the matching row in § 4.

## 4. Symptom → cause → fix matrix

Network-layer symptoms only. For application-layer / SDK / quota issues
see § 8 (cross-references).

| Symptom | Likely cause | Diagnostic | Fix |
|---|---|---|---|
| `InvalidPrivateDnsZoneIds` at `az deployment group create` time | Deployment principal lacks `Private DNS Zone Contributor` on one of the 6 hub PDZs | `az role assignment list --assignee <deployer-objectId> --scope /subscriptions/<dnsSub>/resourceGroups/<dnsRg>/providers/Microsoft.Network/privateDnsZones/<zone> -o table` | Grant `Private DNS Zone Contributor` on each zone in the hub subscription (see § 5). Cap: per-zone, not RG-wide. |
| `Subnet 'agent-subnet' is already in use by capability host` on a second deploy into the same VNet | Caphost subnet still bound by a `serviceAssociationLink` from a prior caphost / account; soft-delete or caphost-only DELETE does **not** release it | `az network vnet subnet show … --query serviceAssociationLinks` returns non-empty | Full account purge — see `foundry-caphost-lifecycle § 8` for the verified GA CLI sequence and § 9 for the redeploy guard. |
| Agent inference returns HTTP 503 within ~1s, no trace in AppInsights | No private endpoint to the AI Services account from the spoke OR PE exists but DNS zone not VNet-linked | Run § 3 step 3 (enumerate PEs) and step 7 (Resolve-DnsName). PE missing = no row for AIServices in step 3. Zone unlinked = step 7 returns a public IP. | Add the missing PE via `az network private-endpoint create --group-id account --private-connection-resource-id <accountId>`, then `az network private-dns link vnet create` for `privatelink.cognitiveservices.azure.com`, `privatelink.openai.azure.com`, `privatelink.services.ai.azure.com`. |
| Agent inference hangs ≥ 30s then times out (no HTTP status, no body) | NSG on the agent subnet (or PE subnet) drops egress 443 to the PE private IP | NSG flow logs (§ 6 query A) or `az network nsg rule list -g $RG --nsg-name $NSG -o table` looking for explicit `Deny *:443` outbound | Add an `Allow *:443 outbound to <peSubnetCidr>` rule **above** any deny. Re-test from a Bastion VM with `Test-NetConnection -Port 443 -ComputerName <acct>.cognitiveservices.azure.com`. |
| `Resolve-DnsName` from inside the spoke returns the public Foundry IP (cloud edge) | PDZ exists somewhere but no VNet link to the spoke VNet, OR link is on the wrong zone name (e.g. `privatelink.openai.azure.com` linked but `privatelink.cognitiveservices.azure.com` not) | `az network private-dns link vnet list --zone-name <zone> -g <dnsRg> -o table` for each of the 6 expected zones | `az network private-dns link vnet create --zone-name <zone> -g <dnsRg> --name <spoke>-link --virtual-network <spokeVnetId> --registration-enabled false` for the missing zone(s). 6 zones expected: `services.ai.azure.com`, `openai.azure.com`, `cognitiveservices.azure.com`, `search.windows.net`, `blob.core.windows.net`, `documents.azure.com`. |
| Hosted-agent create 403 with `MI provisioning failed` | The caller user / SP lacks `Managed Identity Operator` on the Foundry account | `az role assignment list --assignee <callerObjectId> --scope /subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.CognitiveServices/accounts/$ACCT -o table` | Grant per `foundry-vnet-deploy § 8b`. Propagation: 5-15 min. |
| Hosted-agent create 403 with `NIC provisioning failed` | The caller lacks `Network Contributor` on the agent injection subnet | Same as above, but scope is `/subscriptions/$SUB/resourceGroups/$VNET_RG/providers/Microsoft.Network/virtualNetworks/$VNET/subnets/$AGENT_SUBNET` | Grant `Network Contributor` per `foundry-vnet-deploy § 8b`. **Do not** grant at VNet scope — minimum needed is the subnet. |
| APIM call (from inside Foundry, through Citadel hub) returns 404 / 503 | `privatelink.azure-api.net` PDZ not linked to the spoke VNet, so the APIM hostname resolves to a public IP unreachable from the private-only spoke | `Resolve-DnsName <apim>.azure-api.net` from the spoke → public IP = unlinked. `az network private-dns link vnet list --zone-name privatelink.azure-api.net -g <hubDnsRg>` confirms. | Link the zone to the spoke VNet (one-shot `az network private-dns link vnet create`). See `citadel-spoke-onboarding` for the canonical command including the JWT-product-policy follow-up. |
| Project connection (Storage / Cosmos / AISearch) shows red in portal, agent runtime returns 403 on access | Target resource still has `publicNetworkAccess: Enabled` OR PE connection is `Pending` (not Approved) OR the project MI lacks the data-plane role | `az storage account show -n $STG --query "{public:publicNetworkAccess, peConns:privateEndpointConnections[].privateLinkServiceConnectionState.status}"` (analogous for Cosmos / Search) | Set `publicNetworkAccess: Disabled` once the PE is approved. Approve any `Pending` PE with `az network private-endpoint-connection approve …`. RBAC: per `foundry-vnet-deploy § 11.10` (6 role assignments). |
| VNet peering shows `Disconnected` after a recent change | Other-side peering was deleted, OR an address-space update on one side broke the contract (overlap, or shrink), OR cross-tenant peering credential expired | `az network vnet peering show -g $RG --vnet-name $VNET -n $PEER --query peeringState` | Both sides must re-peer. Spoke side: delete + recreate `az network vnet peering`. Hub side: ask hub team to re-run their reverse-peering command (`foundry-vnet-deploy § 8d` emits the `hubReversePeeringCommand` output for this). Verify address-space prefixes haven't drifted. |
| `Subnet 'agent-subnet' delegation 'Microsoft.App/environments' not allowed` on first deploy | Region doesn't yet have `Microsoft.App` registered, or the subnet was pre-created without the delegation | `az provider show -n Microsoft.App --query registrationState` and `az network vnet subnet show … --query delegations` | `az provider register -n Microsoft.App` (idempotent, takes 1-5 min). Add the delegation: `az network vnet subnet update … --delegations Microsoft.App/environments`. |

> **Matrix discipline.** The matrix is **deliberately capped at 10
> rows**. If a symptom is application-layer (model returns wrong text,
> SDK raises a TypeError, AppInsights shows the call but with bad data),
> it goes in § 8, not here.

## 5. Pre-flight at scale (cross-subscription DNS)

When the spoke is deployed into an enterprise hub-and-spoke topology,
the 6 Foundry private DNS zones are typically owned by the **platform
team in a separate connectivity hub subscription**. The deployment
principal needs RBAC in **both** subscriptions — one for the spoke
resources, one for the hub PDZs — or the deploy fails with
`InvalidPrivateDnsZoneIds`. This is the canonical hub-and-spoke pattern
documented in [CAF — Private Link and DNS integration at scale](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/private-link-and-dns-integration-at-scale#private-link-and-dns-integration-in-hub-and-spoke-network-architectures).

| Subscription | Resource | Required role | Why |
|---|---|---|---|
| Spoke (workload) | Spoke resource group | `Contributor` (or finer-grained `Cognitive Services Contributor` + `Network Contributor`) | Deploy the AI Services account, project, model deployment, spoke VNet, PEs, NICs |
| Spoke (workload) | Spoke VNet | `Network Contributor` | Subnet delegation `Microsoft.App/environments`, PE NIC injection, agent NIC creation |
| Hub (connectivity) | Each of the 6 `privatelink.*` PDZs (or `privatelink.azure-api.net` if Citadel) | `Private DNS Zone Contributor` (per-zone, NOT RG-wide) | Create the VNet link from each zone to the spoke VNet so `Resolve-DnsName` from the spoke returns private IPs |
| Hub (connectivity) | Hub VNet | `Network Contributor` (on the hub side, for the hub team) | Create the **reverse** hub→spoke peering (Citadel only — see `foundry-vnet-deploy § 8d`) |
| Foundry account scope | The AI Services account | `Managed Identity Operator` (caller of hosted-agent create) | Per-user grant; provisioning of agent-instance MIs |
| Agent subnet scope | The injection subnet | `Network Contributor` (caller of hosted-agent create) | Per-user grant; agent NIC creation in the delegated subnet |

If the deploy fails with `InvalidPrivateDnsZoneIds`, run this in the
**hub subscription** to confirm the grant exists:

```bash
az account set -s "$HUB_SUB"
az role assignment list \
  --assignee "$DEPLOYER_OBJECT_ID" \
  --scope "/subscriptions/${HUB_SUB}/resourceGroups/${HUB_DNS_RG}/providers/Microsoft.Network/privateDnsZones/privatelink.cognitiveservices.azure.com" \
  -o table
```

If empty, ask the hub team to grant on all 6 zones (or all 7 if Citadel
APIM is in scope). Propagation: 5-15 min before retry.

## 6. Diagnostic Kusto queries

All four queries assume a Log Analytics workspace receives diagnostic
logs from the network resources (NSG flow logs v2, Azure Firewall, the
Cognitive Services account). If a query returns "table not found", the
diagnostic setting is missing — that is a Day-0 setup gap, not a
runtime failure. See `foundry-observability` for diagnostic-setting
wiring.

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

> **Fallback when NSG flow logs v2 isn't enabled** — use
> `AzureDiagnostics | where Category == 'NetworkSecurityGroupFlowEvent'`
> and parse the embedded JSON. v1 is significantly noisier; enabling v2
> is preferred (`az network watcher flow-log create --location <r>
> --enabled-nsg <nsgId> --workspace <lawId> --version 2`).

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

If you see denies, add an Application Rule allowing the matching FQDNs
(prefer the FQDN form over the IP — the private endpoint IP can rotate
on the platform side without notice).

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

This filter narrows to the role classes relevant to network-layer
diagnostics (DNS, NSG, MI, Cog Services). Empty result for the
expected roles is the smoking gun.

## 7. Health checks (recurring)

Schedule these as weekly cron checks (or as part of an Azure Function /
Logic App / scheduled Pipeline). They catch slow drift — a peering that
went `Disconnected` overnight, a missing VNet link after a hub team
rotation, public-access flipped back on by a "compliance" pipeline.

```bash
# H1: All spoke peerings must be Connected
az network vnet peering list -g "$RG" --vnet-name "$VNET" \
  --query "[].peeringState" -o tsv | sort -u
# Expect: a single line `Connected`. Anything else = page on-call.
```

```bash
# H2: All 6 Foundry PDZs have an active VNet link to the spoke
for z in privatelink.services.ai.azure.com privatelink.openai.azure.com \
         privatelink.cognitiveservices.azure.com privatelink.search.windows.net \
         privatelink.blob.core.windows.net privatelink.documents.azure.com; do
  found=$(az network private-dns link vnet list \
    -g "$DNS_RG" --zone-name "$z" \
    --query "[?virtualNetwork.id=='${SPOKE_VNET_ID}'].provisioningState" -o tsv)
  printf "%-50s %s\n" "$z" "${found:-MISSING}"
done
# Expect: every line ends in `Succeeded`.
```

```bash
# H3: All private endpoints in the spoke RG are Approved
az network private-endpoint list -g "$RG" \
  --query "[?privateLinkServiceConnections[0].privateLinkServiceConnectionState.status!='Approved'].name" -o tsv
# Expect: empty output. Any name printed = PE pending / disconnected.
```

```bash
# H4: Public network access disabled on the AI Services account
az rest --method GET \
  --url "https://management.azure.com/subscriptions/${SUB}/resourceGroups/${RG}/providers/Microsoft.CognitiveServices/accounts/${ACCT}?api-version=2025-04-01-preview" \
  --query "properties.publicNetworkAccess" -o tsv
# Expect: Disabled. Enabled = either intentional opening or compliance pipeline flipped it.
```

```bash
# H5: Project MI still has the 5 ARM roles + 1 Cosmos SQL role from § 11.10
PRINCIPAL_ID=$(az rest --method GET \
  --url "https://management.azure.com/subscriptions/${SUB}/resourceGroups/${RG}/providers/Microsoft.CognitiveServices/accounts/${ACCT}/projects/${PROJ}?api-version=2025-04-01-preview" \
  --query "identity.principalId" -o tsv)
az role assignment list --assignee "$PRINCIPAL_ID" --all \
  --query "length([?contains(roleDefinitionName, 'Storage Blob') || contains(roleDefinitionName, 'Cosmos DB') || contains(roleDefinitionName, 'Search')])" -o tsv
# Expect: >= 5. Lower = a cleanup pipeline removed something.
```

```bash
# H6: Agent subnet SAL still bound to the live caphost (not stale-but-not-purged)
az network vnet subnet show \
  -g "$VNET_RG" --vnet-name "$VNET" -n "$AGENT_SUBNET" \
  --query "serviceAssociationLinks[].name" -o tsv
# Expect: exactly one SAL pointing at the current Microsoft.App ME.
# Empty = caphost gone (next deploy will work). Multiple = ops bug — purge stale account.
```

## 8. Cross-references

This runbook covers **network-layer** symptoms only. For symptoms outside
that scope, follow the pointers below — each one cites a specific
section, not the whole skill.

- **`foundry-vnet-deploy § 11`** (post-deployment verification — 11.1
  through 11.11). The Day-0 verification matrix every deploy MUST pass
  before this runbook applies. If § 11 is failing, the issue is a
  deploy-time bug, not a runtime one.
- **`foundry-vnet-deploy § Step 8`** (private DNS zones — central DNS
  at scale). Source of truth for the cross-subscription PDZ shape and
  the `dnsZonesSubscriptionId` parameter.
- **`foundry-vnet-deploy § Step 8b`** (hosted-agent developer RBAC).
  Source of truth for the two per-user grants this runbook's § 4
  references for `MI provisioning failed` and `NIC provisioning failed`.
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
- [Azure Private Endpoint DNS configuration](https://learn.microsoft.com/azure/private-link/private-endpoint-dns) — authoritative list of `privatelink.*` zone names per Azure resource type; verify your 6 Foundry zones match.
- [Foundry — How to use a custom virtual network](https://learn.microsoft.com/azure/foundry/agents/how-to/virtual-networks) — how the AI Services account's `networkInjections` property and the agent subnet delegation `Microsoft.App/environments` fit together.
- [Foundry — Hosted agent permissions](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agent-permissions) — source of truth for the `Managed Identity Operator` + `Network Contributor` grants the § 4 matrix references for hosted-agent create 403s.
- [Azure CLI — `cognitiveservices account`](https://learn.microsoft.com/cli/azure/cognitiveservices/account) — GA reference for the `delete` / `purge` / `list-deleted` / `show-deleted` commands the matrix points at for stale-SAL recovery.
- [NSG flow logs (v2)](https://learn.microsoft.com/azure/network-watcher/network-watcher-nsg-flow-logging-overview) — schema for `AzureNetworkAnalytics_CL` (query A in § 6); enable v2 before relying on the query.
